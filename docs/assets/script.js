// Interactive functionality for research paper website

document.addEventListener('DOMContentLoaded', function() {
    initializeInteractiveFeatures();
    initializeFigureModal();
    initializeScrollToTop();
    initializeEquationLinks();
});

function initializeInteractiveFeatures() {
    // Smooth scrolling for navigation links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
    
    // Highlight current section in navigation
    const sections = document.querySelectorAll('.content-section');
    const navLinks = document.querySelectorAll('.table-of-contents a');
    
    if (sections.length > 0 && navLinks.length > 0) {
        window.addEventListener('scroll', function() {
            let current = '';
            
            sections.forEach(section => {
                const sectionTop = section.offsetTop;
                if (pageYOffset >= sectionTop - 60) {
                    current = section.getAttribute('id');
                }
            });
            
            navLinks.forEach(link => {
                link.classList.remove('active');
                if (link.getAttribute('href') === '#' + current) {
                    link.classList.add('active');
                }
            });
        });
    }
}

function initializeFigureModal() {
    const modal = document.getElementById('figure-modal');
    if (!modal) return;
    
    const closeBtn = document.querySelector('.close');
    
    // Close modal when clicking the close button
    closeBtn.addEventListener('click', function() {
        modal.style.display = 'none';
    });
    
    // Close modal when clicking outside the image
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            modal.style.display = 'none';
        }
    });
    
    // Close modal with Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && modal.style.display === 'block') {
            modal.style.display = 'none';
        }
    });
}

function openFigureModal(img) {
    const modal = document.getElementById('figure-modal');
    const modalImg = document.getElementById('modal-image');
    const modalCaption = document.getElementById('modal-caption');
    
    if (modal && modalImg && modalCaption) {
        modal.style.display = 'block';
        modalImg.src = img.src;
        modalImg.alt = img.alt;
        
        // Get caption from the figure
        const figure = img.closest('.figure');
        const caption = figure.querySelector('.figure-caption');
        if (caption) {
            modalCaption.innerHTML = caption.innerHTML;
        }
    }
}

function initializeScrollToTop() {
    // Create scroll to top button
    const scrollBtn = document.createElement('button');
    scrollBtn.innerHTML = '↑';
    scrollBtn.className = 'scroll-to-top';
    scrollBtn.setAttribute('aria-label', 'Scroll to top');
    document.body.appendChild(scrollBtn);
    
    // Show/hide scroll to top button
    window.addEventListener('scroll', function() {
        if (window.pageYOffset > 300) {
            scrollBtn.classList.add('visible');
        } else {
            scrollBtn.classList.remove('visible');
        }
    });
    
    // Scroll to top when clicked
    scrollBtn.addEventListener('click', function() {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });
}

function initializeEquationLinks() {
    // Add click handlers to equations for easy linking
    document.querySelectorAll('.equation').forEach((eq, index) => {
        eq.addEventListener('click', function() {
            const equationNumber = index + 1;
            const url = new URL(window.location);
            url.hash = `eq-${equationNumber}`;
            
            // Update URL without scrolling
            history.pushState(null, null, url.toString());
            
            // Copy to clipboard
            navigator.clipboard.writeText(url.toString()).then(function() {
                showToast('Equation link copied to clipboard!');
            }).catch(function() {
                // Fallback for browsers that don't support clipboard API
                console.log('Equation link: ' + url.toString());
            });
        });
    });
}

function showToast(message, duration = 3000) {
    // Create toast element
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    
    // Add to page
    document.body.appendChild(toast);
    
    // Show toast
    setTimeout(() => {
        toast.classList.add('show');
    }, 100);
    
    // Hide and remove toast
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            document.body.removeChild(toast);
        }, 300);
    }, duration);
}

// Utility functions for interactive features
function highlightText(text, searchTerm) {
    if (!searchTerm) return text;
    
    const regex = new RegExp(`(${searchTerm})`, 'gi');
    return text.replace(regex, '<mark>$1</mark>');
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Export functions for use in other scripts
window.PaperUtils = {
    openFigureModal,
    showToast,
    highlightText,
    debounce
};