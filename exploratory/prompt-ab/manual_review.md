# Preliminary 10-case prompt review

Condition labels are visible. Judge findings are claims, not independently validated labels.

## 1. HumanEval/33 / run30-step-386-candidate-2 — largest score disagreement

```python
def sort_third(l: list):
    # Extract elements at indices divisible by 3
    sorted_elements = sorted(l[i] for i in range(0, len(l), 3))
    
    # Create a copy of the original list
    result = l.copy()
    
    # Place the sorted elements back at indices divisible by 3
    sorted_idx = 0
    for i in range(0, len(l), 3):
        result[i] = sorted_elements[sorted_idx]
        sorted_idx += 1
        
    return result
```

### HISTORICAL_PROMPT: J=0.65

```json
[
  {
    "category": "Readability",
    "subcategory": "Sub-readable Code Exists",
    "severity": "medium",
    "line_start": 3,
    "line_end": 12,
    "evidence": "sorted_elements = sorted(l[i] for i in range(0, len(l), 3)) ... for i in range(0, len(l), 3): ... result[i] = sorted_elements[sorted_idx]",
    "reason": "The code uses a separate step to extract and sort elements at indices divisible by 3, followed by another loop to place them back. This can be simplified into a single list comprehension similar to the reference solution."
  }
]
```

### STANDALONE_PROMPT: J=1.00

```json
[]
```

## 2. HumanEval/23 / run30-step-197-candidate-1 — largest score disagreement

```python
def strlen(string: str) -> int:
    """ Return length of given string
    >>> strlen('')
    0
    >>> strlen('abc')
    3
    """
    count = 0
    for _ in string:
        count += 1
    return count
```

### HISTORICAL_PROMPT: J=0.65

```json
[
  {
    "category": "Maintainability",
    "subcategory": "Unnecessary Conditional Block",
    "severity": "medium",
    "line_start": 8,
    "line_end": 11,
    "evidence": "count = 0\nfor _ in string:\ncount += 1\nreturn count",
    "reason": "The candidate code uses a loop to count characters, which can be simplified using the built-in len function without changing behavior."
  }
]
```

### STANDALONE_PROMPT: J=0.85

```json
[
  {
    "category": "Readability",
    "subcategory": "Sub-readable Code Exists",
    "severity": "low",
    "line_start": 8,
    "line_end": 11,
    "evidence": "count = 0\nfor _ in string:\n    count += 1\nreturn count",
    "reason": "The manual counting of characters in a string is less readable than using the built-in `len` function. This could be simplified to `return len(string)`."
  }
]
```

## 3. HumanEval/19 / run30-step-464-candidate-0 — largest score disagreement

```python
from typing import List

def sort_numbers(numbers: str) -> str:
    if not numbers.strip():
        return ""
    
    word_to_num = {
        'zero': 0,
        'one': 1,
        'two': 2,
        'three': 3,
        'four': 4,
        'five': 5,
        'six': 6,
        'seven': 7,
        'eight': 8,
        'nine': 9
    }
    
    num_to_word = {v: k for k, v in word_to_num.items()}
    
    words = numbers.split()
    
    # Convert words to numbers, sort, then convert back
    nums = [word_to_num[word] for word in words]
    nums.sort()
    
    sorted_words = [num_to_word[num] for num in nums]
    
    return ' '.join(sorted_words)
```

### HISTORICAL_PROMPT: J=0.50

```json
[
  {
    "category": "Maintainability",
    "subcategory": "Code Duplication",
    "severity": "medium",
    "line_start": 7,
    "line_end": 18,
    "evidence": "word_to_num = {'zero': 0, 'one': 1, ... 'nine': 9}",
    "reason": "The dictionary 'word_to_num' and its reverse 'num_to_word' contain redundant information. This duplication can be avoided by using a single dictionary and reversing it when needed."
  },
  {
    "category": "Readability",
    "subcategory": "Sub-readable Code Exists",
    "severity": "low",
    "line_start": 25,
    "line_end": 28,
    "evidence": "[word_to_num[word] for word in words]\nnums.sort()\nsorted_words = [num_to_word[num] for num in nums]",
    "reason": "The conversion to numbers, sorting, and conversion back to words can be made more readable by combining these steps into a single, more comprehensible operation."
  }
]
```

### STANDALONE_PROMPT: J=0.70

```json
[
  {
    "category": "Readability",
    "subcategory": "Confusing Variable Naming",
    "severity": "low",
    "line_start": 3,
    "line_end": 3,
    "evidence": "def sort_numbers(numbers: str) -> str:",
    "reason": "The parameter name `numbers` is misleading because it suggests a numeric input, but the function actually expects a string of number words. Renaming it to something like `number_words` would improve clarity."
  },
  {
    "category": "Readability",
    "subcategory": "Sub-readable Code Exists",
    "severity": "low",
    "line_start": 24,
    "line_end": 27,
    "evidence": "# Convert words to numbers, sort, then convert back\nnums = [word_to_num[word] for word in words]\nnums.sort()\nsorted_words = [num_to_word[num] for num in nums]",
    "reason": "The comment on line 24 describes what the following lines do, but the code itself could be more readable by breaking down the process into separate steps with descriptive intermediate variables. For example, using `number_values` instead of `nums` and `sorted_number_words` instead of `sorted_words` would make the purpose clearer."
  }
]
```

## 4. HumanEval/19 / run30-step-464-candidate-2 — largest score disagreement

```python
from typing import List

def sort_numbers(numbers: str) -> str:
    word_to_num = {
        'zero': 0,
        'one': 1,
        'two': 2,
        'three': 3,
        'four': 4,
        'five': 5,
        'six': 6,
        'seven': 7,
        'eight': 8,
        'nine': 9
    }
    
    num_to_word = {v: k for k, v in word_to_num.items()}
    
    if not numbers.strip():
        return ""
    
    words = numbers.split()
    nums = [word_to_num[word] for word in words]
    nums.sort()
    sorted_words = [num_to_word[num] for num in nums]
    
    return " ".join(sorted_words)
```

### HISTORICAL_PROMPT: J=0.50

```json
[
  {
    "category": "Readability",
    "subcategory": "Sub-readable Code Exists",
    "severity": "medium",
    "line_start": 17,
    "line_end": 25,
    "evidence": "num_to_word = {v: k for k, v in word_to_num.items()}",
    "reason": "The creation of the reverse mapping (num_to_word) and subsequent use of it adds unnecessary complexity. The reference solution uses a simpler approach with a lambda function in the sort method."
  },
  {
    "category": "Maintainability",
    "subcategory": "Code Duplication",
    "severity": "low",
    "line_start": 19,
    "line_end": 20,
    "evidence": "if not numbers.strip():\n    return \"\"",
    "reason": "This conditional check for an empty string is somewhat redundant given the simplicity of the problem. The reference solution handles this more succinctly."
  }
]
```

### STANDALONE_PROMPT: J=0.70

```json
[
  {
    "category": "Readability",
    "subcategory": "Confusing Variable Naming",
    "severity": "low",
    "line_start": 3,
    "line_end": 3,
    "evidence": "def sort_numbers(numbers: str) -> str:",
    "reason": "The parameter `numbers` is misleading because it is a string of number words, not actual numbers. A more descriptive name like `number_words` would improve clarity."
  },
  {
    "category": "Maintainability",
    "subcategory": "Unnecessary Conditional Block",
    "severity": "low",
    "line_start": 19,
    "line_end": 20,
    "evidence": "if not numbers.strip():\n    return \"\"",
    "reason": "This conditional block checks for an empty string and returns an empty string. This can be simplified by directly handling the empty string case in the subsequent operations, which already handle empty input gracefully."
  }
]
```

## 5. HumanEval/2 / run30-step-30-candidate-0 — clean versus findings

```python
def truncate_number(number: float) -> float:
    return number - int(number)
```

### HISTORICAL_PROMPT: J=1.00

```json
[]
```

### STANDALONE_PROMPT: J=0.85

```json
[
  {
    "category": "Readability",
    "subcategory": "Confusing Variable Naming",
    "severity": "low",
    "line_start": 1,
    "line_end": 2,
    "evidence": "def truncate_number(number: float) -> float:\n    return number - int(number)",
    "reason": "The variable name 'number' is too generic and does not convey its role clearly. Renaming it to something more descriptive like 'input_number' could improve readability."
  }
]
```

## 6. HumanEval/9 / run30-step-73-candidate-2 — clean versus findings

```python
from typing import List

def rolling_max(numbers: List[int]) -> List[int]:
    if not numbers:
        return []
    
    result = []
    current_max = numbers[0]
    result.append(current_max)
    
    for i in range(1, len(numbers)):
        if numbers[i] > current_max:
            current_max = numbers[i]
        result.append(current_max)
    
    return result
```

### HISTORICAL_PROMPT: J=0.85

```json
[
  {
    "category": "Readability",
    "subcategory": "Sub-readable Code Exists",
    "severity": "low",
    "line_start": 11,
    "line_end": 14,
    "evidence": "for i in range(1, len(numbers)): ... result.append(current_max)",
    "reason": "The use of a for loop with an index (i) and manual updating of the current_max variable can be considered sub-readable. A more readable approach might involve using a more direct iteration over the elements."
  }
]
```

### STANDALONE_PROMPT: J=1.00

```json
[]
```

## 7. HumanEval/9 / run30-step-73-candidate-0 — representative agreement

```python
from typing import List

def rolling_max(numbers: List[int]) -> List[int]:
    if not numbers:
        return []
    
    result = []
    current_max = numbers[0]
    for num in numbers:
        if num > current_max:
            current_max = num
        result.append(current_max)
    
    return result
```

### HISTORICAL_PROMPT: J=1.00

```json
[]
```

### STANDALONE_PROMPT: J=1.00

```json
[]
```

## 8. HumanEval/16 / run30-step-143-candidate-3 — representative agreement

```python
def count_distinct_characters(string: str) -> int:
    return len(set(string.lower()))
```

### HISTORICAL_PROMPT: J=1.00

```json
[]
```

### STANDALONE_PROMPT: J=1.00

```json
[]
```

## 9. HumanEval/33 / run30-step-149-candidate-2 — additional disagreement/coverage

```python
def sort_third(l: list):
    """This function takes a list l and returns a list l' such that
    l' is identical to l in the indicies that are not divisible by three, while its values at the indicies that are divisible by three are equal
    to the values of the corresponding indicies of l, but sorted.
    >>> sort_third([1, 2, 3])
    [1, 2, 3]
    >>> sort_third([5, 6, 3, 4, 8, 9, 2])
    [2, 6, 3, 4, 8, 9, 5]
    """
    # Identify indices divisible by 3
    div3_indices = [i for i in range(len(l)) if i % 3 == 0]
    
    # Extract values at those indices
    div3_values = [l[i] for i in div3_indices]
    
    # Sort those values
    div3_values.sort()
    
    # Create a copy of the list
    l_prime = l.copy()
    
    # Place sorted values back at the divisible by 3 indices
    for idx, val in zip(div3_indices, div3_values):
        l_prime[idx] = val
        
    return l_prime
```

### HISTORICAL_PROMPT: J=0.50

```json
[
  {
    "category": "Readability",
    "subcategory": "Sub-readable Code Exists",
    "severity": "medium",
    "line_start": 11,
    "line_end": 24,
    "evidence": "[i for i in range(len(l)) if i % 3 == 0]",
    "reason": "The code uses multiple steps to identify indices divisible by 3, extract values, sort them, and then place them back. This can be simplified into a single list comprehension, making it easier to follow."
  },
  {
    "category": "Maintainability",
    "subcategory": "Code Duplication",
    "severity": "low",
    "line_start": 11,
    "line_end": 14,
    "evidence": "[i for i in range(len(l)) if i % 3 == 0]",
    "reason": "The process of identifying indices divisible by 3 and extracting values at those indices is separate and could be combined into a single step, reducing duplication."
  }
]
```

### STANDALONE_PROMPT: J=0.70

```json
[
  {
    "category": "Readability",
    "subcategory": "Confusing Variable Naming",
    "severity": "low",
    "line_start": 10,
    "line_end": 10,
    "evidence": "div3_indices = [i for i in range(len(l)) if i % 3 == 0]",
    "reason": "The variable name `div3_indices` is somewhat confusing as it does not clearly indicate that it contains indices divisible by 3. A more descriptive name like `indices_divisible_by_three` would improve readability."
  },
  {
    "category": "Maintainability",
    "subcategory": "Unnecessary Conditional Block",
    "severity": "low",
    "line_start": 22,
    "line_end": 24,
    "evidence": "for idx, val in zip(div3_indices, div3_values):\n    l_prime[idx] = val",
    "reason": "The loop here is unnecessary because we could directly assign the sorted values to the appropriate indices using list slicing. This would simplify the code and reduce the chance of errors."
  }
]
```

## 10. HumanEval/40 / run30-step-262-candidate-0 — additional disagreement/coverage

```python
def triples_sum_to_zero(l: list):
    n = len(l)
    if n < 3:
        return False
    for i in range(n - 2):
        for j in range(i + 1, n - 1):
            for k in range(j + 1, n):
                if l[i] + l[j] + l[k] == 0:
                    return True
    return False
```

### HISTORICAL_PROMPT: J=0.50

```json
[
  {
    "category": "Readability",
    "subcategory": "Sub-readable Code Exists",
    "severity": "medium",
    "line_start": 5,
    "line_end": 9,
    "evidence": "for i in range(n - 2): ... for k in range(j + 1, n): ... if l[i] + l[j] + l[k] == 0: ... return True",
    "reason": "The nested loops and the conditional check can be made more readable by using a more descriptive variable naming and simplifying the loop ranges."
  },
  {
    "category": "Maintainability",
    "subcategory": "Unnecessary Conditional Block",
    "severity": "low",
    "line_start": 3,
    "line_end": 4,
    "evidence": "if n < 3: ... return False",
    "reason": "The early return based on the length check can be simplified by directly starting the loop from a valid range, avoiding the need for this conditional block."
  }
]
```

### STANDALONE_PROMPT: J=0.70

```json
[
  {
    "category": "Readability",
    "subcategory": "Confusing Variable Naming",
    "severity": "low",
    "line_start": 1,
    "line_end": 1,
    "evidence": "def triples_sum_to_zero(l: list):",
    "reason": "The variable name 'l' is too generic and does not convey its purpose clearly. It would be more readable to use a descriptive name such as 'numbers'."
  },
  {
    "category": "Maintainability",
    "subcategory": "Unnecessary Conditional Block",
    "severity": "low",
    "line_start": 3,
    "line_end": 4,
    "evidence": "if n < 3:\n    return False",
    "reason": "This conditional block is unnecessary because the nested loops will naturally handle lists shorter than three elements by not entering the loop. This check can be removed to simplify the function."
  }
]
```

