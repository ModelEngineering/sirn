'''Constraint species.'''

"""
Constraints are 
  1. counts of reaction types in which a species is a reactant or product;
  2. number of autocatalysis reactions for a species.
For induced graphs (is_subset=False), there are only equality constraints.
For noninduced graphs (is_subset=True), there are only inequality constraints.
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
        self.is_subset = is_subset
        self.is_initialized = False
        self._inequality_nmat = NULL_NMAT
        self._equality_nmat = NULL_NMAT
        self._species_constraint_nmat = self._makeSpeciesConstraintMatrix()

    @property
    def equality_nmat(self)->NamedMatrix:
        # This property overrides the parent property
        if not self.is_initialized:
            if self.is_subset:
                self._inequality_nmat = NULL_NMAT
                self._equality_nmat = self._species_constraint_nmat
            else:
                self._equality_nmat = NULL_NMAT
                self._inequality_nmat = self._species_constraint_nmat
            self.is_initialized = True
        return self._equality_nmat
        
    @property
    def inequality_nmat(self)->NamedMatrix:
        # This property overrides the parent property
        if not self.is_initialized:
            if self.is_subset:
                self._equality_nmat = NULL_NMAT
                self._inequality_nmat = self._species_constraint_nmat
            else:
                self._inequality_nmat = NULL_NMAT
                self._equality_nmat = self._species_constraint_nmat
            self.is_initialized = True
        return self._equality_nmat

    def __repr__(self)->str:
        return "Species--" + super().__repr__()
    
    def setSubset(self, is_subset:bool)->None:
        self.is_subset = is_subset
        self.is_initialized = False
    
    def _makeSpeciesReactionConstraintMatrix(self)->NamedMatrix:
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
                i_constraint_str = str(self.reaction_classifications[i_reaction])
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
                           row_description=self.reactant_nmat.column_description,
                           column_description=self.reactant_nmat.row_description,
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
                           row_description=self.reactant_nmat.column_description,
                           column_description=self.reactant_nmat.row_description,
                           column_names=column_names)
        return named_matrix
    
    def _makeSpeciesConstraintMatrix(self)->NamedMatrix:
        """Make the species constraint matrix.

        Returns:
            NamedMatrix: Rows are species, columns are constraints
        """
        return NamedMatrix.hstack([self._makeSpeciesReactionConstraintMatrix(),
                                   self._makeAutocatalysisConstraint()])