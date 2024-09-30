'''Constraint species.'''

"""
Implements the calculation of categorical and enumerated constraints for species.
  Enumerated constraints: 
    counts of reaction types in which a species is a reactant or product
    number of autocatalysis reactions for a species.
"""

from sirn.named_matrix import NamedMatrix # type: ignore
from sirn.constraint import Constraint, ReactionClassification, NULL_NMAT # type: ignore

import numpy as np


#####################################
class SpeciesConstraint(Constraint):

    def __init__(self, reactant_nmat:NamedMatrix, product_nmat:NamedMatrix, is_subset:bool=False):
        """
        Args:
            reactant_nmat (NamedMatrix)
            product_nmat (NamedMatrix)
            is_subset (bool, optional) Consider self as a subset of other.
        """
        super().__init__(reactant_nmat=reactant_nmat, product_nmat=product_nmat)
        #
        self._is_initialized = False
        self._enumerated_nmat = NULL_NMAT
        self._categorical_nmat = NULL_NMAT

    @property
    def enumerated_nmat(self)->NamedMatrix:
        if not self._is_initialized:
            self._enumerated_nmat = NamedMatrix.hstack([self._makeReactantProductConstraintMatrix(),
                  self._makeAutocatalysisConstraint(), self._makeSuccessorConstraintMatrix()])
            self._is_initialized = True
        return self._enumerated_nmat

    @property
    def categorical_nmat(self)->NamedMatrix:
        return self._categorical_nmat

    def __repr__(self)->str:
        return "Species--" + super().__repr__()
    
    def _makeReactantProductConstraintMatrix(self)->NamedMatrix:
        """Make constraints for the reaction classification. These are {R, P} X {ReactionClassifications}
        where R is reactant and P is product.

        Returns:
            NamedMatrix: Rows are species, columns are constraints
        """
        reaction_classifications = [str(c) for c in ReactionClassification.getReactionClassifications()]
        reactant_arrays = []
        product_arrays = []
        for i_species in range(self.num_species):
            reactant_array = np.zeros(len(reaction_classifications))
            product_array = np.zeros(len(reaction_classifications))
            for i_reaction in range(self.num_reaction):
                i_constraint_str = str(self.reaction_classification_arr[i_reaction])
                idx = reaction_classifications.index(i_constraint_str)
                if self.reactant_nmat.values[i_species, i_reaction] > 0:
                    reactant_array[idx] += 1
                if self.product_nmat.values[i_species, i_reaction] > 0:
                    product_array[idx] += 1
            reactant_arrays.append(reactant_array)
            product_arrays.append(product_array)
        # Construct full array and labels
        arrays = np.concatenate([reactant_arrays, product_arrays], axis=1)
        reactant_labels = [f"r_{c}" for c in reaction_classifications]
        product_labels = [f"p_{c}" for c in reaction_classifications]
        column_labels = reactant_labels + product_labels
        # Make the NamedMatrix
        named_matrix = NamedMatrix(np.array(arrays), row_names=self.reactant_nmat.row_names,
                           row_description='species',
                           column_description='constraints',
                           column_names=column_labels)
        return named_matrix
    
    def _makeAutocatalysisConstraint(self)->NamedMatrix:
        """Counts the number of reactions in which a species is both a reactant and product.

        Returns:
            NamedMatrix
        """
        column_names =  ['num_autocatalysis']
        array = self.reactant_nmat.values * self.product_nmat.values > 0
        vector = np.sum(array, axis=1)
        vector = np.reshape(vector, (len(vector), 1))
        named_matrix = NamedMatrix(vector, row_names=self.reactant_nmat.row_names,
                           row_description='species',
                           column_description='constraints',
                           column_names=column_names)
        return named_matrix

    def _makeSuccessorConstraintMatrix(self)->NamedMatrix:
        """Make constructs an enumerated constraint that is the number of species (and routes)
        that are reachable in N steps, where N is 2, 4, 8, 16, 32, 64, 128.

        Returns:
            NamedMatrix: Rows are reactions, columns are constraints by count of reaction type.
              <ReactionType>
        """
        STEPS = np.array(range(5))
        # Create the monopartite graph
        incoming_arr = self.reactant_nmat.values
        outgoing_arr = self.product_nmat.values
        # Calculate immediate successors
        successor_arr = np.sign(np.matmul(incoming_arr, outgoing_arr.T))
        step_arrs:list = []
        for _ in STEPS:
            successor_arr = np.sign(np.matmul(successor_arr, successor_arr.T))
            sum_arr = np.sum(successor_arr, axis=1)
            step_arrs.append(sum_arr)
        step_arr = np.array(step_arrs).T
        # Make the NamedMatrix
        column_names = [f"succ_{n}" for n in STEPS]
        named_matrix = NamedMatrix(step_arr, row_names=self.reactant_nmat.row_names,
                           row_description='species',
                           column_description="constraints",
                           column_names=column_names)
        return named_matrix