# PaperFlow

A complete framework for automatically deploying Overleaf research papers as interactive web pages, similar to [textured-gaussians.github.io](https://textured-gaussians.github.io/).

## 🚀 Quick Start

1. **Use this template** - Click "Use this template" to create your research repository
2. **Connect Overleaf** - Link your Overleaf project to this GitHub repo
3. **Configure** - Update `config.yaml` with your paper details
4. **Write** - Work in Overleaf as usual, changes auto-deploy to GitHub Pages

## 📁 Repository Structure

```
paperflow/
├── .github/
│   └── workflows/
│       ├── deploy.yml           # Main deployment workflow
│       └── overleaf-sync.yml    # Overleaf synchronization
├── src/
│   ├── paper/                   # LaTeX source files (synced from Overleaf)
│   │   ├── main.tex
│   │   ├── sections/
│   │   ├── figures/
│   │   └── bibliography.bib
│   └── web/                     # Web template files
│       ├── templates/
│       ├── assets/
│       └── scripts/
├── docs/                        # Generated website (GitHub Pages)
├── scripts/
│   ├── latex_to_html.py        # LaTeX conversion script
│   ├── build_website.py        # Website builder
│   └── utils/
├── tests/                       # Test files
├── config.yaml                 # Project configuration
├── requirements.txt            # Python dependencies
├── pyproject.toml             # Project metadata and tool configuration
└── README.md
```

## ⚙️ Configuration

### config.yaml

```yaml
# Paper Information
paper:
  title: "Your Research Paper Title"
  authors: 
    - name: "Your Name"
      affiliation: "Your University"
      url: "https://yourwebsite.com"
      email: "your.email@university.edu"
  abstract: "Your paper abstract here..."
  keywords: ["keyword1", "keyword2", "keyword3"]
  arxiv_id: ""  # Optional: arXiv paper ID
  doi: ""       # Optional: DOI
  
# Overleaf Integration
overleaf:
  project_id: "your-overleaf-project-id"
  git_url: "https://git.overleaf.com/your-project-id"
  
# Website Settings
website:
  theme: "modern"  # modern, academic, minimal
  show_pdf: true
  interactive_figures: true
  math_renderer: "katex"  # katex, mathjax
  syntax_highlighting: true
  
# GitHub Pages
pages:
  custom_domain: ""  # Optional: your-domain.com
  cname: false
```

## 🔧 Setup Instructions

### 1. Overleaf Git Integration

1. In your Overleaf project, go to **Menu → Git**
2. Copy the Git URL (looks like: `https://git.overleaf.com/xxxxx`)
3. In this GitHub repo, go to **Settings → Secrets and variables → Actions**
4. Add these secrets:
   - `OVERLEAF_GIT_URL`: Your Overleaf Git URL
   - `OVERLEAF_USERNAME`: Your Overleaf email
   - `OVERLEAF_PASSWORD`: Your Overleaf password (or app password)

### 2. GitHub Pages Setup

1. Go to **Settings → Pages**
2. Source: **Deploy from a branch**
3. Branch: **main → / (root)**
4. Your site will be available at: `https://yourusername.github.io/repository-name`

### 3. First Deployment

1. Update `config.yaml` with your paper details
2. Push changes to trigger the first build
3. Your website will be live in ~2-3 minutes

## 🎨 Website Features

### Modern Research Paper Layout
- Hero section with paper title, authors, and abstract
- Interactive PDF viewer embedded in the page
- Responsive design that works on all devices
- Equation rendering with KaTeX or MathJax
- Citation links and bibliography
- Figure galleries with zoom functionality

### Automatic Updates
- Real-time sync from Overleaf to GitHub
- Automatic rebuilds when you update your paper
- Version tracking with Git history
- PDF generation and web conversion

### SEO Optimized
- Meta tags for social media sharing
- Structured data for Google Scholar
- Fast loading with optimized assets
- Mobile friendly responsive design

## 🛠️ Development

### Local Development

1. **Install dependencies**:
   ```bash
   # Using UV (recommended)
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv pip install -r requirements.txt
   
   # Or using pip
   pip install -r requirements.txt
   ```

2. **Run tests**:
   ```bash
   pytest
   
   # With coverage
   pytest --cov=scripts
   
   # Run specific test types
   pytest -m unit
   pytest -m integration
   ```

3. **Build website locally**:
   ```bash
   python scripts/build_website.py
   ```

4. **Convert LaTeX to HTML**:
   ```bash
   python scripts/latex_to_html.py src/paper/main.tex docs/
   ```

### Code Quality

```bash
# Format code
black scripts/ tests/

# Lint code
flake8 scripts/ tests/

# Type checking
mypy scripts/
```

## 🎨 Customization

### Themes

Choose from pre-built themes in `config.yaml`:

- **modern**: Clean, contemporary design (like textured-gaussians.github.io)
- **academic**: Traditional academic paper layout
- **minimal**: Simple, distraction-free design

### Custom Styling

Edit `src/web/assets/custom.css` to override default styles:

```css
:root {
  --primary-color: #your-color;
  --font-family: 'Your Font', serif;
}

.paper-title {
  font-size: 3rem;
  color: var(--primary-color);
}
```

### Interactive Elements

Add interactive components by including special LaTeX comments:

```latex
% INTERACTIVE_FIGURE: figure1.png
% INTERACTIVE_PLOT: data/results.json
% INTERACTIVE_DEMO: https://your-demo-link.com
```

## 📚 LaTeX Support

### Supported Environments

- Standard document classes (`article`, `report`, `book`)
- Math environments (`equation`, `align`, `gather`)
- Figure environments with captions and labels
- Bibliography with BibTeX
- Custom commands and packages

### Best Practices

1. Use `main.tex` as your main document file
2. Put figures in `figures/` subdirectory
3. Use `bibliography.bib` for references
4. Include alt text for figures: `\caption{Your caption here}`
5. Use semantic LaTeX commands rather than manual formatting

## 🔍 Advanced Features

### Custom Build Process

You can customize the build process by editing `scripts/build_website.py`:

```python
def custom_preprocessing(latex_content):
    # Your custom LaTeX preprocessing
    return modified_content

def custom_postprocessing(html_content):
    # Your custom HTML postprocessing
    return modified_content
```

### Adding New Themes

1. Create a new theme CSS file in `src/web/assets/themes/`
2. Add theme configuration to `scripts/build_website.py`
3. Update `config.yaml` with your new theme name

### Analytics and Tracking

Add analytics by including tracking code in your templates:

```html
<!-- Google Analytics -->
<script async src="https://www.googletagmanager.com/gtag/js?id=GA_MEASUREMENT_ID"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'GA_MEASUREMENT_ID');
</script>
```

## 🚨 Troubleshooting

### Common Issues

1. **Build fails**: Check LaTeX syntax and ensure all files are in the correct locations
2. **Figures not displaying**: Verify figure paths and file extensions
3. **Math not rendering**: Check math renderer configuration and LaTeX math syntax
4. **Sync not working**: Verify Overleaf credentials and Git URL

### Debug Mode

Enable debug mode for detailed build logs:

```bash
DEBUG=1 python scripts/build_website.py
```

### Getting Help

1. Check the [Issues](https://github.com/yourusername/paperflow/issues) page
2. Look at example papers in the `examples/` directory
3. Review the test files in `tests/` for usage examples

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Setup

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Inspired by [textured-gaussians.github.io](https://textured-gaussians.github.io/)
- Built with modern web technologies and LaTeX
- Special thanks to the open science community

## 📞 Support

- 📧 Email: your.email@example.com
- 🐛 Issues: [GitHub Issues](https://github.com/yourusername/paperflow/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/yourusername/paperflow/discussions)

---

**Made with ❤️ for the research community**