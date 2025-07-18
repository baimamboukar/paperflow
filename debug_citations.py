#!/usr/bin/env python3

import re

# Test the exact citation processing we're using
test_text = "This is a test \\cite{wertz2011space} with citation and another \\cite{nasa2019europa} here."

print("Original text:")
print(test_text)

# Apply our citation replacement
result = re.sub(r"\\cite\{([^}]+)\}", r'<span class="citation">[\1]</span>', test_text)

print("\nAfter citation replacement:")
print(result)

# Check if there are any issues
if "wertz2011space" in result and "nasa2019europa" in result:
    print("\n✅ Citations are correctly processed")
else:
    print("\n❌ Citations are broken")