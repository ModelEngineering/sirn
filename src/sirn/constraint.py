'''Constraint objects for subgraphs.'''

"""
Constraint objects have two kinds of constraints:
   1. Equality constraints that must have an exact match.
   2. Inequality constaints where the reference must have a value no greater than its target.

Constraints are NamedMatrices such that the columns are constraints and the rows are instances.
For reaction networks, instances are either species or reactions.

Subclasses are responsible for implementing:
  property: numerical_categorical_nmat - NamedMatrix of categorical constraints
  property: numerical_enumerated_nmat - NamedMatrix of enumerated constraints
  property: one_step_nmat - NamedMatrix of one step transitions
  property: logical_categorical_nmat - NamedMatrix of logical (boolean) constraints
  property: logical_enumerated_nmat - NamedMatrix of logical (boolean) constraints such that the target
    must have a one bit for every bit in the reference.
"""

import scipy.special  # type: ignore
import sirn.constants as cn # type: ignore
from sirn.named_matrix import NamedMatrix # type: ignore

import itertools
import json
import numpy as np
import scipy  # type: ignore
from typing import List, Tuple

NULL_NMAT = NamedMatrix(np.array([[]]))
NULL_INT = -1


#####################################
class CompatibilityCollection(object):
    # A compatibility collection specifies the rows in self that are compatible with other.

    def __init__(self, num_self_row:int, num_other_row:int):
        self.num_self_row = num_self_row
        self.num_other_row = num_other_row
        self.compatibilities:list = [ [] for _ in range(num_self_row)]

    def add(self, reference_row:int, target_rows:List[int]):
        # Add rows in target that are compatible with a row in reference
        self.compatibilities[reference_row].extend(target_rows)

    def copy(self)->'CompatibilityCollection':
        new_collection = CompatibilityCollection(self.num_self_row, self.num_other_row)
        new_collection.compatibilities = [l.copy() for l in self.compatibilities]
        return new_collection

    def __repr__(self):
        return str(self.compatibilities)
    
    def __len__(self)->int:
        return len(self.compatibilities)

    def __eq__(self, other)->bool:
        if len(self.compatibilities) != len(other.compatibilities):
            return False
        trues = [np.all(self.compatibilities[i] == other.compatibilities[i]) for i in range(len(self.compatibilities))]
        return bool(np.all(trues))
     
    @property
    def log10_num_permutation(self)->float:
        # Calculates the log of the number of permutations implied by the compatibility collection
        lengths = [len(l) for l in self.compatibilities]
        if 0 in lengths:
            return -np.inf
        return np.sum([np.log10(len(l)) for l in self.compatibilities])
    
    def expand(self)->np.ndarray:
        # Expands the compatibilities into a two dimensional array where each row is a permutation
        return  np.array(list(itertools.product(*self.compatibilities)))

    def prune(self, log10_max_permutation:float)->Tuple['CompatibilityCollection', bool]:
        """Randomly prune the compatibility collection to a maximum number of permutations

        Args:
            log10_max_permutation (float): log10 of the maximum number of permutations

        Returns:
            CompatibilityCollection
        """
        collection = self.copy()
        #
        is_changed = False
        for idx in range(1000000):
            if collection.log10_num_permutation <= log10_max_permutation:
                break
            candidate_rows = [i for i in range(collection.num_self_row)
                              if len(collection.compatibilities[i]) > 1]  
            idx = np.random.randint(0, len(candidate_rows))
            irow = candidate_rows[idx]
            if len(collection.compatibilities[irow]) <= 1:
                continue
            # Check for duplicate single values
            pos = np.random.randint(0, len(collection.compatibilities[irow]))
            singles = list(np.array([v for v in collection.compatibilities if len(v) == 1]).flatten())
            lst = collection.compatibilities[irow][0:pos]
            lst.extend(collection.compatibilities[irow][pos+1:])
            if (len(lst) == 1) and (lst[0] in singles):
                continue
            # Delete the element
            del collection.compatibilities[irow][pos]
            is_changed = True
        else:
            raise ValueError("Could not prune the collection.")
        #
        return collection, is_changed


#####################################
class ReactionClassification(object):
    MAX_REACTANT = 3
    MAX_PRODUCT = 3
    MAX_ENCODING = 1000
    LABELS = ["null", "uni", "bi", "multi"]
    REACTION_CLASSES:List['ReactionClassification'] = []

    def __init__(self, num_reactant:int, num_product:int):
        self.num_reactant = num_reactant
        self.num_product = num_product
        if num_reactant > self.MAX_ENCODING:
            raise ValueError(f"num_reactant must be less than {self.MAX_ENCODING}.")
        if num_product > self.MAX_ENCODING:
            raise ValueError(f"num_product must be less than {self.MAX_ENCODING}.")
        self.encoding = self.num_reactant*100 + self.num_product

    def __repr__(self)->str:
        result = f"{self.LABELS[int(self.num_reactant)]}-{self.LABELS[int(self.num_product)]}"
        return result

    @classmethod 
    def getReactionClassifications(cls)->List['ReactionClassification']:
        """Gets a list of reaction classifications."""
        if len(cls.REACTION_CLASSES) > 0:
            return cls.REACTION_CLASSES
        pairs = [(n, m) for n in range(cls.MAX_REACTANT+1) for m in range(cls.MAX_PRODUCT+1)]
        for num_reactant, num_product in pairs:
            cls.REACTION_CLASSES.append(cls(num_reactant, num_product))
        return cls.REACTION_CLASSES
    

#####################################
class Constraint(object):

    def __init__(self, reactant_nmat:NamedMatrix, product_nmat:NamedMatrix, is_subset:bool=True):
        """
        Args:
            reactant_nmat: NamedMatrix
            product_nmat: NamedMatrix
            num_row: int
            num_column: int
        """
        self.reactant_nmat = reactant_nmat
        self.product_nmat = product_nmat
        self.is_subset = is_subset
        # Calculated
        self._reaction_classes = ReactionClassification.getReactionClassifications()
        self.num_species, self.num_reaction = self.reactant_nmat.num_row, self.reactant_nmat.num_column
        self.reaction_classification_arr = self.classifyReactions()
        # Outputs are categorical_nmat and enumerated_nmat, which are implemented by subclass
        self._is_subset_initialized = False
        self._equality_nmat = NULL_NMAT
        self._inequality_nmat = NULL_NMAT

    @property
    def num_row(self)->int:
        return self.one_step_nmat.num_row

    @classmethod
    def calculateLog10UnconstrainedPermutation(cls, reference_size:int, target_size:int)->float:
        """Calculates the log10 of the number of permutations to examine if no constraint is applied.

        Args:
            reference_size: int (number of species and reactions)
            target_size: int (number of species and reactions)

        Returns:
            float
        """
        def calculatePermutation(num_reference:int, num_target:int)->int:
            result = scipy.special.factorial(num_target) /  \
                  scipy.special.factorial(num_target - num_reference, exact=True)
            return result
        log_permutation = np.log10(calculatePermutation(reference_size, target_size))
        return 2*log_permutation
    
    ################ SUBCLASS MUST IMPLEMENT ################
        
    @property
    def numerical_categorical_nmat(self)->NamedMatrix:
        raise NotImplementedError("numerical_categorical_nmat be implemented by subclass.")
    
    @property
    def numerical_enumerated_nmat(self)->NamedMatrix:
        raise NotImplementedError("numerical_enumerated_nmat be implemented by subclass.")

    @property
    def bitwise_categorical_nmat(self)->NamedMatrix:
        raise NotImplementedError("logical_categorical_nmat be implemented by subclass.")
    
    @property
    def bitwise_enumerated_nmat(self)->NamedMatrix:
        raise NotImplementedError("logical_enumerated_nmat be implemented by subclass.")
    
    @property
    def one_step_nmat(self)->NamedMatrix:
        raise NotImplementedError("one_step_nmat be implemented by subclass.")

    ########################################################
    
    def _initializeSubset(self):
        # Initialize the equality and inequality NamedMatrices
        if self._is_subset_initialized:
            return
        if self.is_subset:
            self._equality_nmat = self.numerical_categorical_nmat
            self._inequality_nmat = self.numerical_enumerated_nmat
            self._equality_nmat.values = self._equality_nmat.values.astype(int)
            self._inequality_nmat.values = self._inequality_nmat.values.astype(int)
        else:
            if self.numerical_categorical_nmat == NULL_NMAT:
                self._equality_nmat = self.numerical_enumerated_nmat
            elif self.numerical_enumerated_nmat == NULL_NMAT:
                self._equality_nmat = self.numerical_categorical_nmat
            else:
                self._equality_nmat = NamedMatrix.hstack([self.numerical_categorical_nmat, self.numerical_enumerated_nmat])
            self._equality_nmat.values = self._equality_nmat.values.astype(int)
            self._inequality_nmat = NULL_NMAT
        self._is_subset_initialized = True
   
    @property
    def equality_nmat(self)->NamedMatrix:
        self._initializeSubset()
        return self._equality_nmat
    
    @property
    def inequality_nmat(self)->NamedMatrix:
        self._initializeSubset()
        return self._inequality_nmat

    def __repr__(self)->str:
        return "Categorical\n" + str(self.numerical_categorical_nmat) + "\n\nEnumerated\n" +  str(self.numerical_enumerated_nmat)

    def __eq__(self, other)->bool:
        if self.__class__.__name__ != other.__class__.__name__:
            return False
        if self.reactant_nmat != other.reactant_nmat:
            return False
        if self.product_nmat != other.product_nmat:
            return False
        return True
    
    def setSubset(self, is_subset:bool)->None:
        self.is_subset = is_subset
        self._is_subset_initialized = False

    def copy(self):
        return self.__class__(self.reactant_nmat.copy(), self.product_nmat.copy())
    
    def serialize(self)->str:
        """Serializes the boundary values."""
        return json.dumps({cn.S_ID: self.__class__.__name__,
                           cn.S_REACTANT_NMAT: self.reactant_nmat.serialize(),
                           cn.S_PRODUCT_NMAT: self.product_nmat.serialize(),
                           })

    @classmethod
    def deserialize(cls, string:str)->'Constraint':
        """Deserializes the boundary values."""
        dct = json.loads(string)
        if not cls.__name__ in dct[cn.S_ID]:
            raise ValueError(f"Expected {cls} but got {dct[cn.S_ID]}")
        reactant_nmat = NamedMatrix.deserialize(dct[cn.S_REACTANT_NMAT])
        product_nmat = NamedMatrix.deserialize(dct[cn.S_PRODUCT_NMAT])
        return cls(reactant_nmat, product_nmat)
    
    def classifyReactions(self)->List[ReactionClassification]:
        """Classify the reactions based on the number of reactants and products.

        Returns:
            List[ReactionClassification]
        """
        classifications = []
        for idx in range(self.num_reaction):
            num_reactant = np.sum(self.reactant_nmat.values[:, idx])
            num_product = np.sum(self.product_nmat.values[:, idx])
            classifications.append(ReactionClassification(num_reactant, num_product))
        return classifications

    @classmethod 
    def calculateBooleanCompatibilityVector(cls, self_constraint_nmat:NamedMatrix,
              other_constraint_nmat:NamedMatrix, is_equality:bool=True)->np.ndarray[bool]:  # type: ignore
        """
        Calculates the compatibility of two matrices of constraints.

        Args:
            other: Constraint
            is_equality: bool (default: True) Equality or inequality

        Returns:
            np.ndarray[bool] - vector of booleans
                index n represents i*self_num_row + jth row in other
        """
        if self_constraint_nmat.num_column != other_constraint_nmat.num_column:
            raise ValueError("Incompatible number of columns.")
        #
        self_num_row = self_constraint_nmat.num_row
        other_num_row = other_constraint_nmat.num_row
        # Check for a null
        num_column = other_constraint_nmat.num_column
        # Calculate the CompatibilityCollection
        #    Create the self array with repeated blocks of each row
        self_arr = np.concatenate([self_constraint_nmat.values]*other_num_row, axis=1)
        self_arr = np.reshape(self_arr, (self_num_row*other_num_row, num_column))
        #    Create the other array with all values of each row
        other_arr = np.reshape(other_constraint_nmat.values, other_num_row*num_column)
        other_arr = np.concatenate([other_arr]*self_num_row)
        other_arr = np.reshape(other_arr, (self_num_row*other_num_row, num_column))
        # Calculate the compatibility boolean vector
        if is_equality:
            satisfy_arr = self_arr == other_arr
        else:
            satisfy_arr = self_arr <= other_arr
        return np.sum(satisfy_arr, axis=1) == num_column
    
    def makeCompatibilityCollection(self, other:'Constraint')->CompatibilityCollection:
        """
        Makes a collection of compatible constraints.
        """
        # Calculate the compatibility of the constraints
        if self.equality_nmat != NULL_NMAT:
            is_equality_compatibility = True
            equality_compatibility_arr = self.calculateBooleanCompatibilityVector(self.equality_nmat,
                  other.equality_nmat, is_equality=True)
        else:
            is_equality_compatibility = False
        if self.inequality_nmat != NULL_NMAT:
            is_inequality_compatibility = True
            inequality_compatibility_arr = self.calculateBooleanCompatibilityVector(self.inequality_nmat,
                  other.inequality_nmat, is_equality=False)
        else:
            is_inequality_compatibility = False
        # Calculate the compatibility vector by combining the equality and inequality constraints
        if is_equality_compatibility and is_inequality_compatibility:
            compatibility_arr = equality_compatibility_arr & inequality_compatibility_arr
        elif is_equality_compatibility:
            compatibility_arr = equality_compatibility_arr
        elif is_inequality_compatibility:
            compatibility_arr = inequality_compatibility_arr
        else:
            raise ValueError("No compatibility constraints.")
        # Create the compatibility collection
        compatibility_collection = CompatibilityCollection(self.num_row, other.num_row)
        target_arr = np.array(range(other.num_row))
        for irow in range(self.num_row):
            #  Select the rows in other that are compatible with the row in self
            base_pos = irow*other.num_row
            idxs = np.array(range(base_pos, base_pos+other.num_row))
            sel_idxs = compatibility_arr[idxs]
            target_rows = target_arr[sel_idxs]
            compatibility_collection.add(irow, target_rows)
        return compatibility_collection
    
    def makeSuccessorPredecessorConstraintMatrix(self)->NamedMatrix:
        """Make a marix of count of successor and predecessor counts. Uses
        subclass.one_step_arr to calculate the counts.

        Returns:
            NamedMatrix: Rows are reactions, columns are constraints by count of reaction type.
              <ReactionType>
        """
        NUM_TRAVERSAL = 2
        def makeTraversalCounts(one_step_arr):
            # one_step_arr: N X N where row is current and column is next
            # Returns: N X NUM_TRAVERSAL where row is current and column is count of next
            multistep_arr = one_step_arr.copy()
            # Process the steps
            count_arrs:list = []  # type: ignore
            count_arrs.append(multistep_arr.sum(axis=1).astype(int))
            for _ in range(2, NUM_TRAVERSAL+1):
                multistep_arr = np.sign(np.matmul(multistep_arr, one_step_arr)).astype(int)
                count_arrs.append(multistep_arr.sum(axis=1))
            count_arr = np.array(count_arrs).T
            return count_arr.astype(int)
        #####
        column_names = [f"s_{n+1}" for n in range(NUM_TRAVERSAL)]
        column_names.extend([f"p_{n+1}" for n in range(NUM_TRAVERSAL)])
        # Calculate successor and predecessor arrays
        successor_count_arr = makeTraversalCounts(self.one_step_nmat.values)
        predecessor_count_arr = makeTraversalCounts(self.one_step_nmat.values.T)
        count_arr = np.concatenate([successor_count_arr, predecessor_count_arr], axis=1).astype(int)
        # Make the NamedMatrix
        named_matrix = NamedMatrix(count_arr, row_names=self.one_step_nmat.row_names,
                           row_description=self.one_step_nmat.row_description,
                           column_description="constraints",
                           column_names=column_names)
        return named_matrix
    
#####################################
NULL_CONSTRAINT = Constraint(NULL_NMAT, NULL_NMAT)