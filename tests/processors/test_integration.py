"""Integration tests for the complete LaTeX to HTML conversion pipeline."""

import pytest
import tempfile
from pathlib import Path
from paperflow.processors.latex.html_converter import HTMLConverter
from paperflow.models.processor import ProcessorConfig, MathRenderer, CitationStyle


class TestIntegration:
    """Integration tests for the complete conversion pipeline."""
    
    def setup_method(self):
        """Set up test environment."""
        self.converter = HTMLConverter()
    
    def test_complete_paper_conversion(self):
        """Test converting a complete academic paper."""
        # Create a comprehensive LaTeX document
        latex_content = r"""
        \documentclass[11pt]{article}
        \usepackage{amsmath}
        \usepackage{graphicx}
        \usepackage{cite}
        
        \title{Machine Learning Approaches to Data Analysis: A Comprehensive Study}
        \author{Dr. Alice Johnson\thanks{University of Technology} \and 
                Prof. Bob Smith\thanks{Institute of Science}}
        
        \begin{document}
        \maketitle
        
        \begin{abstract}
        This paper presents a comprehensive analysis of machine learning approaches 
        for data analysis. We introduce novel algorithms and demonstrate their 
        effectiveness through extensive experiments. Our results show significant 
        improvements over existing methods with up to 15\% better accuracy.
        \end{abstract}
        
        \section{Introduction}
        \label{sec:intro}
        
        Machine learning has revolutionized data analysis \cite{bishop2006,hastie2009}.
        Recent advances in \textbf{deep learning} have shown \emph{remarkable} results
        in various domains \citep{lecun2015,goodfellow2016}.
        
        The main contributions of this work are:
        \begin{itemize}
        \item Novel algorithm design
        \item Comprehensive evaluation
        \item Performance improvements
        \end{itemize}
        
        \subsection{Problem Statement}
        
        We address the challenge of \texttt{efficient} data processing.
        
        \section{Methodology}
        \label{sec:method}
        
        Our approach combines traditional methods with modern techniques.
        
        \subsection{Algorithm Design}
        
        The core algorithm is based on the optimization problem:
        \begin{equation}
        \min_{w} \frac{1}{2} ||w||^2 + C \sum_{i=1}^{n} \xi_i
        \label{eq:optimization}
        \end{equation}
        
        where $w$ represents the weight vector and $\xi_i$ are slack variables.
        
        \subsection{Implementation Details}
        
        The algorithm complexity is $O(n \log n)$ for $n$ data points.
        
        \section{Experiments}
        \label{sec:experiments}
        
        We conducted extensive experiments on multiple datasets.
        
        \begin{figure}[htbp]
        \centering
        \includegraphics[width=0.8\textwidth]{results_comparison.png}
        \caption{Comparison of accuracy across different methods. Our approach 
                 (shown in blue) consistently outperforms baseline methods.}
        \label{fig:results}
        \end{figure}
        
        Figure~\ref{fig:results} shows the experimental results. As can be seen,
        our method achieves superior performance.
        
        \subsection{Dataset Description}
        
        We used three benchmark datasets:
        \begin{enumerate}
        \item Dataset A: 10,000 samples
        \item Dataset B: 50,000 samples  
        \item Dataset C: 100,000 samples
        \end{enumerate}
        
        \subsection{Results Analysis}
        
        The results demonstrate the effectiveness of our approach.
        Equation~\ref{eq:optimization} provides the theoretical foundation.
        
        \section{Related Work}
        \label{sec:related}
        
        Previous work by \citet{zhang2018} explored similar problems.
        However, their approach \cite{wang2019,liu2020} had limitations.
        
        \section{Conclusion}
        \label{sec:conclusion}
        
        We presented a novel machine learning approach that achieves 
        state-of-the-art results. Future work will explore extensions
        to other domains.
        
        \section*{Acknowledgments}
        
        We thank the anonymous reviewers for their valuable feedback.
        
        \bibliography{references}
        \bibliographystyle{plain}
        
        \end{document}
        """
        
        # Create mock bibliography content
        bib_content = r"""
        @book{bishop2006,
          title={Pattern Recognition and Machine Learning},
          author={Bishop, Christopher M},
          year={2006},
          publisher={Springer}
        }
        
        @book{hastie2009,
          title={The Elements of Statistical Learning},
          author={Hastie, Trevor and Tibshirani, Robert and Friedman, Jerome},
          year={2009},
          publisher={Springer}
        }
        
        @article{lecun2015,
          title={Deep learning},
          author={LeCun, Yann and Bengio, Yoshua and Hinton, Geoffrey},
          journal={Nature},
          volume={521},
          number={7553},
          pages={436--444},
          year={2015}
        }
        
        @book{goodfellow2016,
          title={Deep Learning},
          author={Goodfellow, Ian and Bengio, Yoshua and Courville, Aaron},
          year={2016},
          publisher={MIT Press}
        }
        
        @article{zhang2018,
          title={Advanced Machine Learning Methods},
          author={Zhang, Wei and Li, Ming},
          journal={Journal of AI Research},
          volume={45},
          pages={123--145},
          year={2018}
        }
        
        @inproceedings{wang2019,
          title={Efficient Data Processing Algorithms},
          author={Wang, John and Brown, Sarah},
          booktitle={Proceedings of ICML},
          pages={567--578},
          year={2019}
        }
        
        @article{liu2020,
          title={Scalable Learning Systems},
          author={Liu, Chen and Davis, Mike},
          journal={Machine Learning Journal},
          volume={78},
          number={3},
          pages={234--256},
          year={2020}
        }
        """
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Write LaTeX file
            latex_file = temp_path / "paper.tex"
            with open(latex_file, 'w', encoding='utf-8') as f:
                f.write(latex_content)
            
            # Write bibliography file
            bib_file = temp_path / "references.bib"
            with open(bib_file, 'w', encoding='utf-8') as f:
                f.write(bib_content)
            
            # Convert to HTML
            html_file = temp_path / "paper.html"
            result = self.converter.convert_file(
                latex_file, 
                html_file, 
                bibliography_files=[bib_file]
            )
            
            assert result.is_successful, f"Conversion failed: {result.errors}"
            assert result.html_document is not None
            assert html_file.exists()
            
            # Read generated HTML
            html_content = html_file.read_text(encoding='utf-8')
            
            # Comprehensive checks
            self._check_document_structure(html_content)
            self._check_content_conversion(html_content)
            self._check_mathematics(html_content)
            self._check_figures(html_content)
            self._check_citations(html_content)
            self._check_cross_references(html_content)
            self._check_formatting(html_content)
            self._check_responsive_design(html_content)
    
    def _check_document_structure(self, html_content):
        """Check basic HTML document structure."""
        assert "<!DOCTYPE html>" in html_content
        assert "<html lang=\"en\">" in html_content
        assert "<head>" in html_content
        assert "<body>" in html_content
        assert "<article class=\"paper\">" in html_content
        
        # Check title and meta
        assert "Machine Learning Approaches to Data Analysis" in html_content
        assert "charset=\"utf-8\"" in html_content
        assert "viewport" in html_content
    
    def _check_content_conversion(self, html_content):
        """Check content conversion."""
        # Check authors
        assert "Dr. Alice Johnson" in html_content
        assert "Prof. Bob Smith" in html_content
        
        # Check abstract
        assert "comprehensive analysis" in html_content
        assert "15% better accuracy" in html_content
        
        # Check sections
        assert "<h2" in html_content  # Section headings
        assert "Introduction" in html_content
        assert "Methodology" in html_content
        assert "Experiments" in html_content
        assert "Conclusion" in html_content
        
        # Check subsections
        assert "<h3" in html_content  # Subsection headings
        assert "Problem Statement" in html_content
        assert "Algorithm Design" in html_content
    
    def _check_mathematics(self, html_content):
        """Check mathematical content."""
        # Check inline math
        assert "\\(n \\log n\\)" in html_content or "$n \\log n$" in html_content
        assert "\\(w\\)" in html_content or "$w$" in html_content
        
        # Check display equations
        assert "min_{w}" in html_content or "\\min_{w}" in html_content
        assert "xi_i" in html_content or "\\xi_i" in html_content
        
        # Check equation labels/references
        assert "eq:optimization" in html_content or "Equation" in html_content
    
    def _check_figures(self, html_content):
        """Check figure handling."""
        assert "<figure" in html_content
        assert "<img" in html_content
        assert "<figcaption" in html_content
        assert "results_comparison.png" in html_content
        assert "Comparison of accuracy" in html_content
        assert "fig:results" in html_content or "Figure" in html_content
    
    def _check_citations(self, html_content):
        """Check citation processing."""
        # Check bibliography section
        assert "References" in html_content
        assert "Bishop, Christopher" in html_content
        assert "Pattern Recognition and Machine Learning" in html_content
        assert "LeCun, Yann" in html_content
        assert "Deep learning" in html_content
        
        # Check citation links
        assert 'class="citation"' in html_content
        assert "[1]" in html_content or "[2]" in html_content
    
    def _check_cross_references(self, html_content):
        """Check cross-reference handling."""
        # Check section references
        assert 'href="#' in html_content
        
        # Check figure references
        assert "Figure" in html_content
        
        # Check equation references  
        assert "Equation" in html_content
    
    def _check_formatting(self, html_content):
        """Check text formatting."""
        assert "<strong>deep learning</strong>" in html_content
        assert "<em>remarkable</em>" in html_content
        assert "<code>efficient</code>" in html_content
        
        # Check lists
        assert "<ul>" in html_content or "<ol>" in html_content
        assert "<li>" in html_content
    
    def _check_responsive_design(self, html_content):
        """Check responsive design elements."""
        assert "@media" in html_content
        assert "max-width" in html_content
        assert "viewport" in html_content
    
    def test_conversion_with_errors(self):
        """Test conversion handling with various errors."""
        # Test with missing bibliography file
        latex_content = r"""
        \title{Test}
        \section{Test}
        Citation test \cite{missing_ref}.
        \bibliography{nonexistent}
        """
        
        result = self.converter.latex_parser.parse_content(latex_content)
        html_result = self.converter.convert_document(result.latex_document)
        
        # Should still produce HTML despite missing bibliography
        assert html_result.html_document is not None
        # May have warnings
        assert len(html_result.warnings) >= 0
    
    def test_different_configurations(self):
        """Test conversion with different configurations."""
        configs = [
            ProcessorConfig(math_renderer=MathRenderer.MATHJAX),
            ProcessorConfig(math_renderer=MathRenderer.KATEX),
            ProcessorConfig(citation_style=CitationStyle.IEEE),
            ProcessorConfig(citation_style=CitationStyle.APA),
        ]
        
        latex_content = r"""
        \title{Config Test}
        \section{Test}
        Math: $x = y$ and \cite{ref1}.
        """
        
        for config in configs:
            converter = HTMLConverter(config)
            parse_result = converter.latex_parser.parse_content(latex_content)
            html_result = converter.convert_document(parse_result.latex_document)
            
            assert html_result.is_successful
            assert html_result.html_document is not None
            
            # Check that configuration is reflected
            html_content = html_result.html_document.html_content
            
            if config.math_renderer == MathRenderer.KATEX:
                assert "katex" in html_content.lower()
            else:
                assert "mathjax" in html_content.lower()

    def test_large_document_performance(self):
        """Test performance with a large document."""
        # Generate a large document with many sections
        sections = []
        for i in range(50):
            sections.append(f"""
            \\section{{Section {i+1}}}
            This is section {i+1} with some content. It includes math $x_{i+1} = y_{i+1}$
            and references to \\cite{{ref{i+1}}}.
            
            \\subsection{{Subsection {i+1}.1}}
            More content with equations:
            \\begin{{equation}}
            f_{i+1}(x) = ax^2 + bx + c_{i+1}
            \\end{{equation}}
            """)
        
        large_latex = f"""
        \\title{{Large Document Test}}
        \\author{{Test Author}}
        
        \\begin{{abstract}}
        This is a large document for performance testing.
        \\end{{abstract}}
        
        {''.join(sections)}
        
        \\section{{Conclusion}}
        This concludes our large document test.
        """
        
        import time
        start_time = time.time()
        
        parse_result = self.converter.latex_parser.parse_content(large_latex)
        html_result = self.converter.convert_document(parse_result.latex_document)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        assert html_result.is_successful
        assert html_result.html_document is not None
        
        # Performance should be reasonable (less than 10 seconds for 50 sections)
        assert processing_time < 10.0
        
        # Check that all sections were processed
        html_content = html_result.html_document.html_content
        assert "Section 1" in html_content
        assert "Section 50" in html_content
        assert "Conclusion" in html_content