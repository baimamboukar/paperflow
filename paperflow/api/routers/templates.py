"""
Templates router for Paperflow API.

This module provides endpoints for template and theme management,
including listing, installing, and applying templates to projects.
"""

from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    status
)

from paperflow.api.dependencies import (
    get_current_user,
    get_project_service,
    require_authentication,
    validate_project_id,
)
from paperflow.api.schemas.base import APIResponse, PaginationParams
from paperflow.api.schemas.templates import (
    TemplateApply,
    TemplateApplyResponse,
    TemplateCategory,
    TemplateCreate,
    TemplateEngine,
    TemplateFilter,
    TemplateInstall,
    TemplateInstallResponse,
    TemplateLicense,
    TemplateListResponse,
    TemplateRating,
    TemplateRatingResponse,
    TemplateResponse,
    TemplateSort,
    TemplateStatsResponse,
    TemplateType,
    TemplateUpdate,
    TemplateValidationResponse,
)
from paperflow.services.project_service import ProjectService
from paperflow.utils.logging import setup_logging

logger = setup_logging(__name__)

router = APIRouter()


@router.get("", response_model=TemplateListResponse)
async def list_templates(
    pagination: PaginationParams = Depends(),
    filters: TemplateFilter = Depends(),
    sort: TemplateSort = Depends(),
    project_service: ProjectService = Depends(get_project_service),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """
    List available templates with filtering and pagination.
    
    Supports filtering by:
    - Type, category, engine, license
    - Tags, author, search query
    - Minimum rating, LaTeX engine compatibility
    
    Supports sorting by various fields.
    """
    try:
        logger.info(f"Listing templates with filters: {filters.dict(exclude_unset=True)}")
        
        # Get templates from service
        templates, total = await project_service.list_templates(
            offset=pagination.offset,
            limit=pagination.page_size,
            filters=filters.dict(exclude_unset=True),
            sort_by=sort.sort_by,
            sort_order=sort.sort_order,
        )
        
        # Create paginated response
        paginated_response = TemplateListResponse.create(
            items=templates,
            total=total,
            pagination=pagination
        )
        
        return TemplateListResponse(
            success=True,
            message=f"Found {total} templates",
            data=paginated_response,
        )
        
    except Exception as e:
        logger.error(f"Error listing templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error listing templates"
        )


@router.get("/{template_name}", response_model=TemplateResponse)
async def get_template(
    template_name: str,
    version: Optional[str] = Query(None, description="Specific template version"),
    project_service: ProjectService = Depends(get_project_service),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """Get detailed information about a specific template."""
    try:
        logger.info(f"Getting template: {template_name}")
        
        # Get template
        template = await project_service.get_template(
            template_name=template_name,
            version=version
        )
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template '{template_name}' not found"
            )
        
        return TemplateResponse(
            success=True,
            message=f"Template '{template_name}' retrieved successfully",
            data=template,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting template {template_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving template"
        )


@router.post("/{template_name}/install", response_model=TemplateInstallResponse)
async def install_template(
    template_name: str,
    install_request: TemplateInstall,
    background_tasks: BackgroundTasks,
    project_service: ProjectService = Depends(get_project_service),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """
    Install a template to the local template library.
    
    Downloads and installs the template, making it available
    for use in project creation and application.
    """
    try:
        logger.info(f"Installing template: {template_name}")
        
        # Validate template exists
        template = await project_service.get_template(
            template_name=template_name,
            version=install_request.version
        )
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template '{template_name}' not found"
            )
        
        # Check if already installed
        if await project_service.is_template_installed(template_name, install_request.version):
            if not install_request.overwrite:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Template '{template_name}' is already installed"
                )
        
        # Schedule background installation
        background_tasks.add_task(
            _install_template_background,
            project_service=project_service,
            template_name=template_name,
            install_request=install_request,
            user_id=current_user.get("user_id")
        )
        
        return TemplateInstallResponse(
            success=True,
            message=f"Template '{template_name}' installation initiated"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error installing template {template_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error installing template: {str(e)}"
        )


@router.post("/{template_name}/apply", response_model=TemplateApplyResponse)
async def apply_template(
    template_name: str,
    apply_request: TemplateApply,
    background_tasks: BackgroundTasks,
    project_service: ProjectService = Depends(get_project_service),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """
    Apply a template to create a new project or update an existing one.
    
    Creates project structure, copies template files, and applies
    template variables to generate the final project.
    """
    try:
        logger.info(f"Applying template {template_name} to project {apply_request.project_name}")
        
        # Validate template exists and is installed
        template = await project_service.get_template(template_name)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template '{template_name}' not found"
            )
        
        if not await project_service.is_template_installed(template_name):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Template '{template_name}' is not installed. Install it first."
            )
        
        # Check if target project exists
        project_exists = await project_service.project_exists(apply_request.project_name)
        if project_exists and not apply_request.overwrite_existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Project '{apply_request.project_name}' already exists"
            )
        
        # Validate template variables
        validation_result = await project_service.validate_template_variables(
            template_name=template_name,
            variables=apply_request.variables
        )
        
        if not validation_result.valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Template variables validation failed: {validation_result.errors}"
            )
        
        # Schedule background application
        background_tasks.add_task(
            _apply_template_background,
            project_service=project_service,
            template_name=template_name,
            apply_request=apply_request,
            user_id=current_user.get("user_id")
        )
        
        return TemplateApplyResponse(
            success=True,
            message=f"Template '{template_name}' application to project '{apply_request.project_name}' initiated"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error applying template {template_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error applying template: {str(e)}"
        )


@router.post("/{template_name}/validate", response_model=TemplateValidationResponse)
async def validate_template(
    template_name: str,
    version: Optional[str] = Query(None, description="Specific template version"),
    check_latex: bool = Query(True, description="Check LaTeX compilation"),
    check_packages: bool = Query(True, description="Check required packages"),
    project_service: ProjectService = Depends(get_project_service),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """Validate a template's structure, files, and LaTeX compatibility."""
    try:
        logger.info(f"Validating template: {template_name}")
        
        # Validate template
        validation_result = await project_service.validate_template(
            template_name=template_name,
            version=version,
            check_latex=check_latex,
            check_packages=check_packages
        )
        
        return TemplateValidationResponse(
            success=True,
            message=f"Template '{template_name}' validation completed",
            data=validation_result
        )
        
    except Exception as e:
        logger.error(f"Error validating template {template_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error validating template: {str(e)}"
        )


@router.post("", response_model=TemplateResponse)
async def create_template(
    template_data: TemplateCreate,
    background_tasks: BackgroundTasks,
    project_service: ProjectService = Depends(get_project_service),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """
    Create a new custom template.
    
    Creates a template from a source directory, ZIP file, or Git repository.
    The template will be validated and made available for use.
    """
    try:
        logger.info(f"Creating template: {template_data.metadata.name}")
        
        # Check if template already exists
        if await project_service.template_exists(template_data.metadata.name):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Template '{template_data.metadata.name}' already exists"
            )
        
        # Schedule background creation
        background_tasks.add_task(
            _create_template_background,
            project_service=project_service,
            template_data=template_data,
            user_id=current_user.get("user_id")
        )
        
        # Return template metadata (will be updated when creation completes)
        return TemplateResponse(
            success=True,
            message=f"Template '{template_data.metadata.name}' creation initiated",
            data={
                "metadata": template_data.metadata,
                "files": [],
                "variables": template_data.variables,
                "build_config": template_data.build_config,
                "project_structure": {},
                "preview_images": [],
                "example_output": None
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating template: {str(e)}"
        )


@router.put("/{template_name}", response_model=TemplateResponse)
async def update_template(
    template_name: str,
    template_update: TemplateUpdate,
    project_service: ProjectService = Depends(get_project_service),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """Update an existing template."""
    try:
        logger.info(f"Updating template: {template_name}")
        
        # Check if template exists
        if not await project_service.template_exists(template_name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template '{template_name}' not found"
            )
        
        # Update template
        template = await project_service.update_template(
            template_name=template_name,
            update_data=template_update.dict(exclude_unset=True),
            updated_by=current_user.get("user_id", "unknown")
        )
        
        logger.info(f"Successfully updated template: {template_name}")
        
        return TemplateResponse(
            success=True,
            message=f"Template '{template_name}' updated successfully",
            data=template
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating template {template_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating template: {str(e)}"
        )


@router.delete("/{template_name}")
async def delete_template(
    template_name: str,
    version: Optional[str] = Query(None, description="Specific version to delete"),
    force: bool = Query(False, description="Force deletion even if template is in use"),
    project_service: ProjectService = Depends(get_project_service),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """Delete a template."""
    try:
        logger.info(f"Deleting template: {template_name}")
        
        # Check if template exists
        if not await project_service.template_exists(template_name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template '{template_name}' not found"
            )
        
        # Check if template is in use
        if not force:
            usage_count = await project_service.get_template_usage_count(template_name)
            if usage_count > 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Template '{template_name}' is used by {usage_count} projects. Use force=true to delete anyway."
                )
        
        # Delete template
        await project_service.delete_template(
            template_name=template_name,
            version=version,
            deleted_by=current_user.get("user_id", "unknown")
        )
        
        logger.info(f"Successfully deleted template: {template_name}")
        
        return APIResponse(
            success=True,
            message=f"Template '{template_name}' deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting template {template_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting template: {str(e)}"
        )


@router.post("/{template_name}/rate", response_model=TemplateRatingResponse)
async def rate_template(
    template_name: str,
    rating_data: TemplateRating,
    project_service: ProjectService = Depends(get_project_service),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """Rate a template."""
    try:
        logger.info(f"Rating template {template_name}: {rating_data.rating} stars")
        
        # Check if template exists
        if not await project_service.template_exists(template_name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template '{template_name}' not found"
            )
        
        # Add user information to rating
        rating_data.user = current_user.get("user_id", "unknown")
        rating_data.template_name = template_name
        
        # Submit rating
        rating = await project_service.rate_template(rating_data.dict())
        
        logger.info(f"Successfully rated template {template_name}")
        
        return TemplateRatingResponse(
            success=True,
            message=f"Template '{template_name}' rated successfully",
            data=rating
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rating template {template_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error rating template: {str(e)}"
        )


@router.get("/categories/list")
async def list_template_categories():
    """List all available template categories."""
    try:
        categories = [
            {
                "value": category.value,
                "name": category.value.replace("_", " ").title(),
                "description": f"Templates for {category.value.replace('_', ' ')} purposes"
            }
            for category in TemplateCategory
        ]
        
        return APIResponse(
            success=True,
            message="Template categories retrieved successfully",
            data=categories
        )
        
    except Exception as e:
        logger.error(f"Error listing template categories: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error listing template categories"
        )


@router.get("/types/list")
async def list_template_types():
    """List all available template types."""
    try:
        types = [
            {
                "value": template_type.value,
                "name": template_type.value.replace("_", " ").title(),
                "description": f"Templates for {template_type.value.replace('_', ' ')}"
            }
            for template_type in TemplateType
        ]
        
        return APIResponse(
            success=True,
            message="Template types retrieved successfully",
            data=types
        )
        
    except Exception as e:
        logger.error(f"Error listing template types: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error listing template types"
        )


@router.get("/engines/list")
async def list_template_engines():
    """List all available template engines."""
    try:
        engines = [
            {
                "value": engine.value,
                "name": engine.value.title(),
                "description": f"Templates using {engine.value.upper()}"
            }
            for engine in TemplateEngine
        ]
        
        return APIResponse(
            success=True,
            message="Template engines retrieved successfully",
            data=engines
        )
        
    except Exception as e:
        logger.error(f"Error listing template engines: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error listing template engines"
        )


@router.get("/licenses/list")
async def list_template_licenses():
    """List all available template licenses."""
    try:
        licenses = [
            {
                "value": license_type.value,
                "name": license_type.value.upper().replace("_", " "),
                "description": f"Templates with {license_type.value.upper()} license"
            }
            for license_type in TemplateLicense
        ]
        
        return APIResponse(
            success=True,
            message="Template licenses retrieved successfully",
            data=licenses
        )
        
    except Exception as e:
        logger.error(f"Error listing template licenses: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error listing template licenses"
        )


@router.get("/stats", response_model=TemplateStatsResponse)
async def get_template_stats(
    project_service: ProjectService = Depends(get_project_service),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """Get template usage statistics."""
    try:
        logger.info("Getting template statistics")
        
        # Get template statistics
        stats = await project_service.get_template_statistics()
        
        return TemplateStatsResponse(
            success=True,
            message="Template statistics retrieved successfully",
            data=stats
        )
        
    except Exception as e:
        logger.error(f"Error getting template statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving template statistics"
        )


# Background task functions
async def _install_template_background(
    project_service: ProjectService,
    template_name: str,
    install_request: TemplateInstall,
    user_id: Optional[str]
):
    """Install template in background."""
    try:
        logger.info(f"Installing template in background: {template_name}")
        
        await project_service.install_template(
            template_name=template_name,
            version=install_request.version,
            target_directory=install_request.target_directory,
            overwrite=install_request.overwrite,
            variables=install_request.variables,
            installed_by=user_id
        )
        
        logger.info(f"Template installation completed: {template_name}")
        
    except Exception as e:
        logger.error(f"Template installation failed: {template_name}: {e}")


async def _apply_template_background(
    project_service: ProjectService,
    template_name: str,
    apply_request: TemplateApply,
    user_id: Optional[str]
):
    """Apply template in background."""
    try:
        logger.info(f"Applying template in background: {template_name} -> {apply_request.project_name}")
        
        await project_service.apply_template(
            template_name=template_name,
            project_name=apply_request.project_name,
            variables=apply_request.variables,
            overwrite_existing=apply_request.overwrite_existing,
            backup_existing=apply_request.backup_existing,
            apply_build_config=apply_request.apply_build_config,
            applied_by=user_id
        )
        
        logger.info(f"Template application completed: {template_name} -> {apply_request.project_name}")
        
    except Exception as e:
        logger.error(f"Template application failed: {template_name} -> {apply_request.project_name}: {e}")


async def _create_template_background(
    project_service: ProjectService,
    template_data: TemplateCreate,
    user_id: Optional[str]
):
    """Create template in background."""
    try:
        logger.info(f"Creating template in background: {template_data.metadata.name}")
        
        await project_service.create_template(
            metadata=template_data.metadata.dict(),
            source_type=template_data.source_type,
            source_path=template_data.source_path,
            variables=template_data.variables,
            build_config=template_data.build_config,
            created_by=user_id
        )
        
        logger.info(f"Template creation completed: {template_data.metadata.name}")
        
    except Exception as e:
        logger.error(f"Template creation failed: {template_data.metadata.name}: {e}")