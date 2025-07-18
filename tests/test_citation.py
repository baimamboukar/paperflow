#!/usr/bin/env python3

import re

def test_citation_processing():
    # Test text with citation
    test_text = "This is a test \\cite{wertz2011space} with citation."
    
    print("Original text:", test_text)
    
    # Apply citation replacement
    result = re.sub(r"\\cite\{([^}]+)\}", r"[\1]", test_text)
    
    print("After citation replacement:", result)
    
    return result

if __name__ == "__main__":
    test_citation_processing()