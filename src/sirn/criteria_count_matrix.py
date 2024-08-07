'''Common code for CriteriaCountMatrix counts of occurrences of criteria satisfied in each row.'''

from sirn import constants as cn # type: ignore
from sirn.criteria_vector import CriteriaVector # type: ignore
from sirn.named_matrix import Matrix  # type: ignore
from sirn.named_matrix import NamedMatrix  # type: ignore

import numpy as np
from typing import List, Union, Optional

class CriteriaCountMatrix(Matrix):
    def __init__(self, array:np.array, criteria_vector:Optional[CriteriaVector]=None):
        """
        Args:
            array (np.array): An array of real numbers.
            criteria_vector (CriteriaVector): A vector of criteria.
        """
        self.criteria_vec = criteria_vector
        super().__init__(array)

    def __repr__(self)->str:
        named_matrix = NamedMatrix(self.values, row_name="rows", column_name="criteria")
        return named_matrix.__repr__()
    
    def isEqualValues(self, other)->bool:
        """
        Compare the values of two matrices.
        Args:
            other (CriteriaCountMatrix): Another matrix with same shape.
            max_permutation (int): The maximum number of permutations.
        Returns:
            bool: True if the values are equal.
        """
        return bool(np.all(self.values == other.values))
    
    def isLessEqualValues(self, other)->bool:
        """
        Compare the values of two matrices.
        Args:
            other (CriteriaCountMatrix): Another matrix with same shape.
            max_permutation (int): The maximum number of permutations.
        Returns:
            bool: True if the values are equal.
        """
        return bool(np.all(self.values <= other.values))