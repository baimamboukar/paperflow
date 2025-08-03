"""
Projects router for Paperflow API.

This module provides endpoints for project CRUD operations,
file management, and project validation.
"""

import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter, 
    BackgroundTasks, 
    Depends, 
    File, 
    Form, 
    HTTPException, 
    Query, 
    UploadFile,
    status
)
from fastapi.responses import FileResponse, JSONResponse

from paperflow.api.dependencies import (
    get_current_user,
    get_project_service,
    get_settings,
    get_upload_directory,
    require_authentication,
    validate_file_upload,
    validate_project_id,
)
from paperflow.api.schemas.base import APIResponse, BulkOperationRequest, PaginationParams
from paperflow.api.schemas.project import (
    ProjectCreate,
    ProjectCreateResponse,
    ProjectDeleteResponse,
    ProjectDetailResponse,
    ProjectFileResponse,
    ProjectFileUpload,
    ProjectFilters,
    ProjectListResponse,
    ProjectSort,
    ProjectSummary,
    ProjectUpdate,
    ProjectUpdateResponse,
    ProjectValidation,
    ProjectValidationResponse,
)
from paperflow.config.settings import Settings
from paperflow.services.project_service import ProjectService
from paperflow.utils.logging import setup_logging

logger = setup_logging(__name__)

router = APIRouter()


async def get_project_or_404(
    project_id: str,
    project_service: ProjectService,
    current_user: Optional[Dict[str, Any]] = None
) -> Any:
    """Get project by ID or raise 404 error."""
    try:
        project = await project_service.get_project(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{project_id}' not found"
            )
        
        # TODO: Add permission checks based on current_user
        return project
    
    except Exception as e:
        logger.error(f"Error fetching project {project_id}: {e}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching project"
        )


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    pagination: PaginationParams = Depends(),
    filters: ProjectFilters = Depends(),
    sort: ProjectSort = Depends(),
    project_service: ProjectService = Depends(get_project_service),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """
    List projects with pagination, filtering, and sorting.
    
    Supports filtering by:
    - Status, type, language
    - Search query in name, title, abstract
    - Date ranges
    - Author presence
    
    Supports sorting by various fields with ascending/descending order.
    """
    try:
        logger.info(f"Listing projects with filters: {filters.dict(exclude_unset=True)}")
        
        # Get projects from service
        projects, total = await project_service.list_projects(
            offset=pagination.offset,
            limit=pagination.page_size,
            filters=filters.dict(exclude_unset=True),
            sort_by=sort.sort_by,
            sort_order=sort.sort_order,
        )
        
        # Convert to summaries
        project_summaries = [
            ProjectSummary(
                name=project.name,
                title=project.title,
                status=project.status,
                project_type=project.project_type,
                authors_count=len(project.authors),
                has_abstract=bool(project.abstract),
                keywords_count=len(project.keywords),
                created_at=project.created_at,
                updated_at=project.updated_at,
                last_build=project.last_build,
                last_sync=project.last_sync,
            )
            for project in projects
        ]
        
        # Create paginated response
        paginated_response = ProjectListResponse.create(
            items=project_summaries,
            total=total,
            pagination=pagination
        )
        
        return ProjectListResponse(
            success=True,
            message=f"Found {total} projects",
            data=paginated_response,
        )
        
    except Exception as e:
        logger.error(f"Error listing projects: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error listing projects"
        )


@router.post("", response_model=ProjectCreateResponse)
async def create_project(
    project_data: ProjectCreate,
    background_tasks: BackgroundTasks,
    project_service: ProjectService = Depends(get_project_service),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """
    Create a new project.
    
    Creates project directory structure, initializes configuration,
    and optionally creates template files.
    """
    try:
        logger.info(f"Creating project: {project_data.name}")
        
        # Check if project already exists
        if await project_service.project_exists(project_data.name):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Project '{project_data.name}' already exists"
            )
        
        # Create project
        project = await project_service.create_project(
            project_data=project_data.dict(),
            created_by=current_user.get("user_id", "unknown")
        )
        
        # Schedule background initialization
        background_tasks.add_task(
            project_service.initialize_project_files,
            project.name
        )
        
        logger.info(f"Successfully created project: {project.name}")
        
        return ProjectCreateResponse(
            success=True,
            message=f"Project '{project.name}' created successfully",
            data=project,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating project: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating project: {str(e)}"
        )


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(
    project_id: str = Depends(validate_project_id),
    project_service: ProjectService = Depends(get_project_service),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """Get detailed project information."""
    try:
        project = await get_project_or_404(project_id, project_service, current_user)
        
        logger.info(f"Retrieved project: {project_id}")
        
        return ProjectDetailResponse(
            success=True,
            message=f"Project '{project_id}' retrieved successfully",
            data=project,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving project"
        )


@router.put("/{project_id}", response_model=ProjectUpdateResponse)
async def update_project(
    project_update: ProjectUpdate,
    project_id: str = Depends(validate_project_id),
    project_service: ProjectService = Depends(get_project_service),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """Update project information."""
    try:
        # Verify project exists
        await get_project_or_404(project_id, project_service, current_user)
        
        logger.info(f"Updating project: {project_id}")
        
        # Update project
        project = await project_service.update_project(
            project_id=project_id,
            update_data=project_update.dict(exclude_unset=True),
            updated_by=current_user.get("user_id", "unknown")
        )
        
        logger.info(f"Successfully updated project: {project_id}")
        
        return ProjectUpdateResponse(
            success=True,
            message=f"Project '{project_id}' updated successfully",
            data=project,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating project: {str(e)}"
        )


@router.delete("/{project_id}", response_model=ProjectDeleteResponse)
async def delete_project(
    project_id: str = Depends(validate_project_id),
    force: bool = Query(False, description="Force deletion even if project has dependencies"),
    backup: bool = Query(True, description="Create backup before deletion"),
    project_service: ProjectService = Depends(get_project_service),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """Delete a project."""
    try:
        # Verify project exists
        await get_project_or_404(project_id, project_service, current_user)
        
        logger.info(f"Deleting project: {project_id} (force={force}, backup={backup})")
        
        # Delete project
        await project_service.delete_project(
            project_id=project_id,
            force=force,
            create_backup=backup,
            deleted_by=current_user.get("user_id", "unknown")
        )
        
        logger.info(f"Successfully deleted project: {project_id}")
        
        return ProjectDeleteResponse(
            success=True,
            message=f"Project '{project_id}' deleted successfully",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting project: {str(e)}"
        )


@router.post("/{project_id}/validate", response_model=ProjectValidationResponse)
async def validate_project(
    project_id: str = Depends(validate_project_id),
    check_files: bool = Query(True, description="Check file integrity"),
    check_latex: bool = Query(True, description="Check LaTeX compilation"),
    check_bibliography: bool = Query(True, description="Check bibliography"),
    project_service: ProjectService = Depends(get_project_service),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """Validate project structure, files, and LaTeX compilation."""
    try:
        # Verify project exists
        await get_project_or_404(project_id, project_service, current_user)
        
        logger.info(f"Validating project: {project_id}")
        
        # Perform validation
        validation_result = await project_service.validate_project(
            project_id=project_id,
            check_files=check_files,
            check_latex=check_latex,
            check_bibliography=check_bibliography,
        )
        
        logger.info(f"Project validation completed for: {project_id}")
        
        return ProjectValidationResponse(
            success=True,
            message=f"Project '{project_id}' validation completed",
            data=validation_result,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error validating project: {str(e)}"
        )


@router.get("/{project_id}/files")
async def list_project_files(
    project_id: str = Depends(validate_project_id),
    path: str = Query("", description="Subdirectory path within project"),
    include_hidden: bool = Query(False, description="Include hidden files"),
    file_types: Optional[List[str]] = Query(None, description="Filter by file extensions"),
    project_service: ProjectService = Depends(get_project_service),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """List files in project directory."""
    try:
        # Verify project exists
        project = await get_project_or_404(project_id, project_service, current_user)
        
        logger.info(f"Listing files for project: {project_id}")
        
        # Get project files
        files = await project_service.list_project_files(
            project_id=project_id,
            path=path,
            include_hidden=include_hidden,
            file_types=file_types,
        )
        
        return APIResponse(
            success=True,
            message=f"Listed {len(files)} files for project '{project_id}'",
            data=files,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing files for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error listing project files"
        )


@router.post("/{project_id}/files", response_model=ProjectFileResponse)
async def upload_project_file(
    project_id: str = Depends(validate_project_id),
    file: UploadFile = File(...),
    file_type: str = Form(...),
    destination: Optional[str] = Form(None),
    overwrite: bool = Form(False),
    project_service: ProjectService = Depends(get_project_service),
    upload_dir: Path = Depends(get_upload_directory),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """Upload a file to project."""
    try:
        # Verify project exists
        await get_project_or_404(project_id, project_service, current_user)
        
        # Validate file upload
        validate_file_upload(file.size or 0)
        
        logger.info(f"Uploading file to project {project_id}: {file.filename}")
        
        # Read file content
        content = await file.read()
        
        # Upload file to project
        file_info = await project_service.upload_file(
            project_id=project_id,
            filename=file.filename or "unknown",
            content=content,
            file_type=file_type,
            destination=destination,
            overwrite=overwrite,
            uploaded_by=current_user.get("user_id", "unknown")
        )
        
        logger.info(f"Successfully uploaded file to project {project_id}: {file.filename}")
        
        return ProjectFileResponse(
            success=True,
            message=f"File uploaded successfully to project '{project_id}'",
            data=file_info,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file to project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading file: {str(e)}"
        )


@router.get("/{project_id}/files/{file_path:path}")
async def get_project_file(
    project_id: str = Depends(validate_project_id),
    file_path: str = ...,
    download: bool = Query(False, description="Download file as attachment"),
    project_service: ProjectService = Depends(get_project_service),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """Get or download a project file."""
    try:
        # Verify project exists
        project = await get_project_or_404(project_id, project_service, current_user)
        
        # Get file path
        full_file_path = await project_service.get_file_path(project_id, file_path)
        
        if not full_file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File '{file_path}' not found in project '{project_id}'"
            )
        
        if full_file_path.is_dir():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"'{file_path}' is a directory, not a file"
            )
        
        logger.info(f"Serving file from project {project_id}: {file_path}")
        
        # Return file
        if download:
            return FileResponse(
                path=full_file_path,
                filename=full_file_path.name,
                media_type="application/octet-stream"
            )
        else:
            return FileResponse(path=full_file_path)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting file {file_path} from project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving file"
        )


@router.delete("/{project_id}/files/{file_path:path}")
async def delete_project_file(
    project_id: str = Depends(validate_project_id),
    file_path: str = ...,
    backup: bool = Query(True, description="Create backup before deletion"),
    project_service: ProjectService = Depends(get_project_service),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """Delete a project file."""
    try:
        # Verify project exists
        await get_project_or_404(project_id, project_service, current_user)
        
        logger.info(f"Deleting file from project {project_id}: {file_path}")
        
        # Delete file
        await project_service.delete_file(
            project_id=project_id,
            file_path=file_path,
            create_backup=backup,
            deleted_by=current_user.get("user_id", "unknown")
        )
        
        logger.info(f"Successfully deleted file from project {project_id}: {file_path}")
        
        return APIResponse(
            success=True,
            message=f"File '{file_path}' deleted successfully from project '{project_id}'",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting file {file_path} from project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting file: {str(e)}"
        )


@router.post("/{project_id}/clone")
async def clone_project(
    project_id: str = Depends(validate_project_id),
    new_name: str = Form(...),
    include_files: bool = Form(True),
    include_config: bool = Form(True),
    reset_timestamps: bool = Form(True),
    project_service: ProjectService = Depends(get_project_service),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """Clone an existing project."""
    try:
        # Verify source project exists
        await get_project_or_404(project_id, project_service, current_user)
        
        # Check if target project name is available
        if await project_service.project_exists(new_name):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Project '{new_name}' already exists"
            )
        
        logger.info(f"Cloning project {project_id} to {new_name}")
        
        # Clone project
        cloned_project = await project_service.clone_project(
            source_project_id=project_id,
            new_name=new_name,
            include_files=include_files,
            include_config=include_config,
            reset_timestamps=reset_timestamps,
            cloned_by=current_user.get("user_id", "unknown")
        )
        
        logger.info(f"Successfully cloned project {project_id} to {new_name}")
        
        return ProjectCreateResponse(
            success=True,
            message=f"Project '{project_id}' cloned successfully as '{new_name}'",
            data=cloned_project,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cloning project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error cloning project: {str(e)}"
        )


@router.post("/{project_id}/archive")
async def archive_project(
    project_id: str = Depends(validate_project_id),
    reason: Optional[str] = Form(None),
    project_service: ProjectService = Depends(get_project_service),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """Archive a project."""
    try:
        # Verify project exists
        await get_project_or_404(project_id, project_service, current_user)
        
        logger.info(f"Archiving project: {project_id}")
        
        # Archive project
        await project_service.archive_project(
            project_id=project_id,
            reason=reason,
            archived_by=current_user.get("user_id", "unknown")
        )
        
        logger.info(f"Successfully archived project: {project_id}")
        
        return APIResponse(
            success=True,
            message=f"Project '{project_id}' archived successfully",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error archiving project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error archiving project: {str(e)}"
        )


@router.post("/{project_id}/restore")
async def restore_project(
    project_id: str = Depends(validate_project_id),
    project_service: ProjectService = Depends(get_project_service),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """Restore an archived project."""
    try:
        # Verify project exists
        await get_project_or_404(project_id, project_service, current_user)
        
        logger.info(f"Restoring project: {project_id}")
        
        # Restore project
        await project_service.restore_project(
            project_id=project_id,
            restored_by=current_user.get("user_id", "unknown")
        )
        
        logger.info(f"Successfully restored project: {project_id}")
        
        return APIResponse(
            success=True,
            message=f"Project '{project_id}' restored successfully",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error restoring project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error restoring project: {str(e)}"
        )


@router.get("/{project_id}/export")
async def export_project(
    project_id: str = Depends(validate_project_id),
    format: str = Query("zip", description="Export format: zip, tar"),
    include_source: bool = Query(True, description="Include source files"),
    include_build: bool = Query(True, description="Include build outputs"),
    include_assets: bool = Query(True, description="Include assets"),
    project_service: ProjectService = Depends(get_project_service),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """Export project as archive."""
    try:
        # Verify project exists
        await get_project_or_404(project_id, project_service, current_user)
        
        logger.info(f"Exporting project: {project_id}")
        
        # Export project
        export_path = await project_service.export_project(
            project_id=project_id,
            format=format,
            include_source=include_source,
            include_build=include_build,
            include_assets=include_assets,
        )
        
        logger.info(f"Successfully exported project: {project_id}")
        
        # Return file
        return FileResponse(
            path=export_path,
            filename=f"{project_id}.{format}",
            media_type="application/octet-stream"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error exporting project: {str(e)}"
        )