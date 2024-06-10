'''Describes a set of arrays and their partition constrained permutations.'''

"""
Arrays are classified based on the number of values that are less than 0, equal to 0, and greater than 0.

Terminology:
- Array: A collection of numbers.
- ArrayCollection: A collection of arrays.
- Encoding: A single number that represents the array, a homomorphism (and so is not unique).
"""

import numpy as np

SEPARATOR = 1000 # Separates the counts in a single numbera


class ArrayCollection(object):

    def __init__(self, collection: np.ndarray)->None:
        """
        Args:
            arrays (np.array): A collection of arrays.
        """
        self.collection = collection
        self.narr, self.length = np.shape(collection)
        #
        if (self.length > SEPARATOR):
            raise ValueError("Matrix is too large to classify. Maximum number of rows, columns is 1000.")
        # Outputs
        self.encoding = self.encode()

    def __repr__(self)->str:
        return str(self.encoding)
    
    def isCompatible(self, other)->bool:
        """
        Checks if the two ArrayCollection have the same encoding.

        Args:
            other (_type_): _description_

        Returns:
            bool: _description_
        """
        return np.allclose(self.encoding, other.encoding)

    # This method can be overridden to provide alternative encodings
    def encode(self)->np.ndarray:
        """Constructs an encoding for an ArrayCollection.

        Args:
            arr (np.ndarray): _description_

        Returns:
            np.ndarray: _description_
        """
        encoding = []
        for arr in self.collection:
            term = np.sum(arr < 0) + np.sum(arr == 0) * SEPARATOR + np.sum(arr > 0)*SEPARATOR**2
            encoding.append(term)
        encoding.sort()
        result = np.array(encoding)
        result = result.astype(int)
        return result
    
    def encodingConstrainedIterator(self)->np.ndarray:
        """
        Iterates through all permutations of arrays in the ArrayCollection
        that are constrained by the encoding of the arrays.

        returns:
            np.array-int: A permutation of the arrays.
        """
        raise NotImplementedError()