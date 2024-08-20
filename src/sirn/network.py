'''Central class in the DISRN algorithm. Does analysis of network structures.'''

from sirn import constants as cn  # type: ignore
from sirn import util  # type: ignore
from sirn.criteria_vector import CriteriaVector  # type: ignore
from sirn.matrix import Matrix  # type: ignore
from sirn.pair_criteria_count_matrix import PairCriteriaCountMatrix  # type: ignore
from sirn.single_criteria_count_matrix import SingleCriteriaCountMatrix  # type: ignore
from sirn.network_base import NetworkBase, AssignmentPair  # type: ignore

import copy
import collections
import itertools
import numpy as np
from typing import Optional, Tuple

NULL_ARRAY = np.array([])  # Null array


MAX_PREFIX_LEN = 3   # Maximum length of a prefix in the assignment to do a pairwise analysis
#  assignments: np.ndarray[np.ndarray[int]]
#  is_truncated: bool (True if the number of assignments exceeds the maximum number of assignments)
AssignmentResult = collections.namedtuple('AssignmentResult', 'assignment_arr is_truncated compression_factor')
# Pair of assignments of species and reactions in target network to the reference network.


class StructurallyIdenticalResult(object):
    # Auxiliary object returned by isStructurallyIdentical

    def __init__(self,
                 assignment_pairs:list[AssignmentPair],
                 is_truncated:Optional[bool]=False,
                 species_compression_factor:Optional[float]=None,
                 reaction_compression_factor:Optional[float]=None,
                 )->None:
        """
        Args:
            assignment_pairs (list[AssignmentPair]): List of assignment pairs.
            is_trucnated (bool): True if the number of assignments exceeds the maximum number of assignments.
            species_compression_factor (float): Number of species assignments considered at each step divided by the 
                number of assignments kept
            reaction_compression_factor (float): Number of species assignments considered at each step divided by the 
                number of assignments kept
        """
        self.assignment_pairs = assignment_pairs
        self.is_truncated = is_truncated
        self.species_compression_factor = species_compression_factor
        self.reaction_compression_factor = reaction_compression_factor

    def __bool__(self)->bool:
        return len(self.assignment_pairs) > 0


class Network(NetworkBase):

    def __init__(self, reactant_arr:Matrix, 
                 product_arr:np.ndarray,
                 reaction_names:Optional[np.ndarray[str]]=None,
                 species_names:Optional[np.ndarray[str]]=None,
                 network_name:Optional[str]=None,
                 criteria_vector:Optional[CriteriaVector]=None)->None:
        """
        Args:
            reactant_mat (np.ndarray): Reactant matrix.
            product_mat (np.ndarray): Product matrix.
            network_name (str): Name of the network.
            reaction_names (np.ndarray[str]): Names of the reactions.
            species_names (np.ndarray[str]): Names of the species
        """
        super().__init__(reactant_arr, product_arr, network_name=network_name,
                            reaction_names=reaction_names, species_names=species_names,
                            criteria_vector=criteria_vector) 

    def __eq__(self, other)->bool:
        """
        Args:
            other (Network): Network to compare to.
        Returns:
            bool: True if equal.
        """
        if not isinstance(other, Network):
            return False
        return super().__eq__(other)
    
    def copy(self):
        """
        Returns:
            Network: Copy of this network.
        """
        return Network(self.reactant_mat.values.copy(), self.product_mat.values.copy(),
                        network_name=self.network_name,
                        reaction_names=self.reaction_names,
                        species_names=self.species_names,
                        criteria_vector=self.criteria_vector)
    
    def makeCompatibilitySetVector(self,
          target:'Network',
          orientation:str=cn.OR_SPECIES,
          identity:str=cn.ID_WEAK,
          is_subsets:bool=False,
          )->list[list[int]]:
        """
        Constructs a vector of lists of rows in the target that are compatible with each row in the reference (self).
        Handles the interaction between identity and participant.

        Args:
            target_network (Network): Target network.
            orientation (str): Orientation of the network. cn.OR_REACTIONS or cn.OR_SPECIES.
            identity (str): Identity of the network. cn.ID_WEAK or cn.ID_STRONG.
            participant (str): Participant in the network for ID_STRONG. cn.PR_REACTANT or cn.PR_PRODUCT.
            is_subsets (bool): If True, check for subsets of other.

        Returns:
            list-list: Vector of lists of rows in the target that are compatible with each row in the reference.
        """
        compatible_sets:list = []
        def makeSets(participant:Optional[str]=None):
            reference_matrix = self.getNetworkMatrix(matrix_type=cn.MT_SINGLE_CRITERIA,
                                                      orientation=orientation,
                                                      identity=identity,
                                                      participant=participant)
            target_matrix = target.getNetworkMatrix(matrix_type=cn.MT_SINGLE_CRITERIA,
                                                      orientation=orientation,
                                                      identity=identity,
                                                      participant=participant)
            num_criteria = reference_matrix.num_column
            reference_num_row = reference_matrix.num_row
            target_num_row = target_matrix.num_row
            # Construct two large 2D arrays that allows for simultaneous comparison of all rows 
            big_reference_arr = util.repeatRow(reference_matrix.values, target_num_row)
            big_target_arr = util.repeatArray(target_matrix.values, reference_num_row)
            # Find the compatible sets
            if is_subsets:
                big_compatible_arr = np.less_equal(big_reference_arr, big_target_arr)
            else:
                big_compatible_arr = np.equal(big_reference_arr, big_target_arr)
            satisfy_arr = np.sum(big_compatible_arr, axis=1) == num_criteria
            # Construct the sets
            target_indices = np.array(range(target_num_row))
            for iset in range(reference_num_row):
                indices = target_num_row*iset + target_indices
                compatible_sets[iset] = target_indices[satisfy_arr[indices]].tolist()
            return compatible_sets
        #
        # Check compatibility
        if (not is_subsets) and not self.isStructurallyCompatible(target, identity=identity):
            return compatible_sets
        if is_subsets and not self.isSubsetCompatible(target):
            return compatible_sets
        # Construct the compatibility sets
        if orientation == cn.OR_REACTION:
            this_num_row = self.num_reaction
        else:
            this_num_row = self.num_species
        compatible_sets = [ [] for _ in range(this_num_row)]
        # Find compatible Rows
        if identity == cn.ID_WEAK:
            compatible_sets = makeSets(participant=None)
        else:
            reactant_compatible_sets = makeSets(participant=cn.PR_REACTANT)
            product_compatible_sets = makeSets(participant=cn.PR_PRODUCT)
            for idx in range(this_num_row):
                compatible_sets[idx] = list(set(reactant_compatible_sets[idx]) & set(product_compatible_sets[idx]))
        #
        return compatible_sets

    def makeCompatibleAssignments(self,
                                  target:'Network',
                                  orientation:str=cn.OR_SPECIES,
                                  identity:str=cn.ID_WEAK,
                                  is_subsets:bool=False,
                                  max_num_assignment=cn.MAX_NUM_ASSIGNMENT)->AssignmentResult:
        """
        Constructs a list of compatible assignments. The strategy is to find initial segments
        that are pairwise compatible. Handles strong vs. weak identity by considering both reactant
        and product PairCriteriaCountMatrix for strong identity. At any step in the assignment process,
        the number of assignments is pruned if it exceeds the maximum number of assignments. The pruning
        is done by selecting a random subset of assignments.

        Args:
            target (Network): Target network.
            orientation (str): Orientation of the network. cn.OR_REACTIONS or cn.OR_SPECIES.
            identity (str): Identity of the network. cn.ID_WEAK or cn.ID_STRONG.
            is_subsets (bool): If True, check for subsets of other.
            max_num_assignment (int): Maximum number of assignments.

        Returns:
            AssignmentResult
        """
        NULL_ASSIGNMENT_RESULT = AssignmentResult(assignment_arr=NULL_ARRAY, is_truncated=None,
                                                    compression_factor=None)
        def checkAssignments(pos, assignment_arr:np.ndarray, participant:Optional[str]=None)->np.ndarray:
                """
                Checks if the assignments are compatible with the PairwiseCriteriaCountMatrices of
                the reference and target matrices.
                """
                if assignment_arr.shape[0] == 0:
                    return assignment_arr
                # Get the pair array for the last two columns of the assignment array
                reference_pair_criteria_matrix = self.getNetworkMatrix(matrix_type=cn.MT_PAIR_CRITERIA,
                                                                orientation=orientation,
                                                                identity=identity,
                                                                participant=participant)
                target_pair_criteria_matrix = target.getNetworkMatrix(matrix_type=cn.MT_PAIR_CRITERIA,
                                                                orientation=orientation,
                                                                identity=identity,
                                                                participant=participant)
                num_assignment, assignment_len = assignment_arr.shape
                target_arr = target_pair_criteria_matrix.getTargetArray(assignment_arr)
                base_reference_arr = reference_pair_criteria_matrix.getReferenceArray(assignment_len)
                reference_arr = np.vstack([base_reference_arr]*num_assignment)
                num_column = reference_pair_criteria_matrix.num_column
                if is_subsets:
                    compatible_arr = np.less_equal(reference_arr, target_arr)
                else:
                    compatible_arr = np.equal(reference_arr, target_arr)
                # Find the rows that are compatible
                satisfy_arr = np.sum(compatible_arr, axis=1) == num_column
                # Reshape so can count satisfying each position in the assignment
                satisfy_arr = np.reshape(satisfy_arr, (num_assignment, assignment_len-1))
                satisfy_arr = np.sum(satisfy_arr, axis=1) == assignment_len - 1
                new_assignment_arr = assignment_arr[satisfy_arr, :]
                return new_assignment_arr   
        #
        def prune(assignment_arr, keep_count:Optional[int]=None)->Tuple[np.ndarray, bool]:
            """Prunes the assignments if the number of assignments exceeds the maximum number of assignments.

            Args:
                assignment_arr (_type_): _description_

            Returns:
                Tuple[np.ndarray, bool]: _description_
            """
            is_truncated = False
            if keep_count is None:
                keep_count = max_num_assignment
            if assignment_arr.shape[0] > keep_count:
                select_idx = np.random.choice(assignment_arr.shape[0], keep_count, replace=False)
                assignment_arr = assignment_arr[select_idx, :]
                is_truncated = True
            return assignment_arr, is_truncated
        #
        compatible_sets = self.makeCompatibilitySetVector(target, orientation=orientation, identity=identity,
                                                          is_subsets=is_subsets)
        assignment_len = len(compatible_sets)  # Number of rows in the reference
        # Initialize the 2d array of assignments. Rows are assignment instance and columns are rows in the target.
        if len(compatible_sets) == 0:
            return NULL_ASSIGNMENT_RESULT
        if compatible_sets[0] == 0:
            return NULL_ASSIGNMENT_RESULT
        assignment_arr = np.array(np.array(compatible_sets[0]))
        assignment_arr = np.reshape(assignment_arr, (len(assignment_arr), 1))
           
        # Incrementally extend assignments by the cross product of the compatibility set for each position
        initial_sizes:list = []  # Number of assignments at each step
        final_sizes:list = [] # Number of assignments after cross product and pruning 
        is_truncated = False # True if the set of assignments was truncated because of excessive size
        for pos in range(1, assignment_len):
            # Check if no assignments
            if assignment_arr.shape[0] == 0:
                return NULL_ASSIGNMENT_RESULT
            # Prune the number of assignments if it exceeds the maximum number of assignments
            keep_count = max_num_assignment // len(compatible_sets[pos])
            assignment_arr, new_is_truncated = prune(assignment_arr, keep_count=keep_count)
            if assignment_arr.shape[0] == 0:
                return NULL_ASSIGNMENT_RESULT
            is_truncated = is_truncated or new_is_truncated
            # Extend assignment_arr to the cross product of the compatibility set for this position.$a
            #   This is done by repeating by doing a block repeat of each row in the assignment array
            #   with a block size equal to the number of elements in the compatibility set for compatibility_sets[pos],
            #   and then repeating the compatibility set block for compatibility_sets[pos] for each
            #   row in the assignment array.
            ex_assignment_arr = np.repeat(assignment_arr, len(compatible_sets[pos]), axis=0)
            ex_compatibility_arr = np.vstack([compatible_sets[pos]*len(assignment_arr)]).T
            assignment_arr = np.hstack((ex_assignment_arr, ex_compatibility_arr))
            initial_sizes.append(assignment_arr.shape[0])
            # Find the rows that have a duplicate value. We do this by: (a) sorting the array, (b) finding the
            #   difference between the array and the array shifted by one, (c) finding the product of the differences.
            #   The product of the differences will be zero if there is a duplicate value.
            sorted_arr = np.sort(assignment_arr, axis=1)
            diff_arr = np.diff(sorted_arr, axis=1)
            prod_arr = np.prod(diff_arr, axis=1)
            keep_idx = np.where(prod_arr > 0)[0]
            assignment_arr = assignment_arr[keep_idx, :]
            # Check for pairwise compatibility between the last assignment and the new assignment
            #   This is done by finding the pairwise column for the previous and current assignment.
            #   Then we verify that the reference row is either equal (is_subset=False) or less than or equal (is_subset=True)
            #   the target row.
            if identity == cn.ID_WEAK:
                assignment_arr = checkAssignments(pos, assignment_arr, None)
            else:
                # Strong identity
                # Must satisfy conditions for both reactant and product
                assignment_arr = checkAssignments(pos, assignment_arr, participant=cn.PR_REACTANT)
                assignment_arr = checkAssignments(pos, assignment_arr, participant=cn.PR_PRODUCT)
            final_sizes.append(assignment_arr.shape[0])
        #
        if all([s > 0 for s in final_sizes]):
            compression_factor = np.array(initial_sizes)/np.array(final_sizes)
        else:
            compression_factor = None
        return AssignmentResult(assignment_arr=assignment_arr, is_truncated=is_truncated,
                                compression_factor=compression_factor)
    
    def isStructurallyIdentical(self, target:'Network', is_subsets:bool=False,
            max_num_assignment:int=cn.MAX_NUM_ASSIGNMENT, identity:str=cn.ID_WEAK,
            )->StructurallyIdenticalResult:
        """
        Determines if the network is structurally identical to another network.

        Args:
            target (Network): Network to search for structurally identity
            is_subsets (bool, optional): Consider subsets
            max_num_assignment (int, optional): Maximum number of assignments to produce.
            identity (str, optional): cn.ID_WEAK or cn.ID_STRONG

        Returns:
            StructurallyIdenticalResult: _description_
        """
        MAX_ARRAY_COMPARE = 100000
        NULL_STRUCTURALLY_IDENTICAL_RESULT = StructurallyIdenticalResult(assignment_pairs=[])
        # Get the compatible assignments for species and reactions
        species_assignment_result = self.makeCompatibleAssignments(target, cn.OR_SPECIES, identity=identity,
              is_subsets=is_subsets, max_num_assignment=max_num_assignment)
        species_assignment_arr = species_assignment_result.assignment_arr
        reaction_assignment_result = self.makeCompatibleAssignments(target, cn.OR_REACTION, identity=identity,
              is_subsets=is_subsets, max_num_assignment=max_num_assignment)
        reaction_assignment_arr = reaction_assignment_result.assignment_arr
        is_trucated = species_assignment_result.is_truncated or reaction_assignment_result.is_truncated
        if len(species_assignment_arr) == 0 or len(reaction_assignment_arr) == 0:
            return NULL_STRUCTURALLY_IDENTICAL_RESULT
        # Compare the reference and target matrices for the participant and identity
        def compare(participant:Optional[str]=None)->np.ndarray[bool]:
            """
            Compares the reference matrix to the target matrix for the participant and identity.

            Args:
                participant: cn.PR_REACTANT or cn.PR_PRODUCT

            Returns:
                np.ndarray[bool]: flattened boolean array of the outcome of comparisons for assignments
                                  The array is organized breadth-first (column first).
            """
            reference_matrix = self.getNetworkMatrix(matrix_type=cn.MT_STOICHIOMETRY, orientation=cn.OR_SPECIES,
                  participant=participant, identity=identity)
            target_matrix = target.getNetworkMatrix(matrix_type=cn.MT_STOICHIOMETRY, orientation=cn.OR_SPECIES,
                  participant=participant, identity=identity)
            # Size the comparison arrays used to make comparisons
            num_species_assignment =  len(species_assignment_result.assignment_arr)
            num_reaction_assignment =  len(reaction_assignment_result.assignment_arr)
            num_assignment =  num_species_assignment*num_reaction_assignment
            if num_assignment > MAX_ARRAY_COMPARE:
                raise ValueError(f"Number of assignments exceeds {MAX_ARRAY_COMPARE}.")
            # Set up the comparison arrays. These are referred to as 'big' arrays.
            big_reference_arr = np.vstack([reference_matrix.values]*num_assignment)
            species_idxs = species_assignment_arr.flatten()
            reaction_idxs = reaction_assignment_arr.flatten()
            #   The following constructs the re-arranged target matrix.
            #   This is organized as blocks of row rearrangements (species) and
            #   each row rearrangement is repeated for several columns (reactions) rearrangements.
            big_reaction_idxs = np.vstack([reaction_idxs]*len(species_idxs)).flatten()
            big_species_idxs = np.repeat(species_idxs, len(reaction_idxs))
            flattened_big_target_arr = target_matrix.values[big_species_idxs, big_reaction_idxs]
            big_target_arr = np.reshape(flattened_big_target_arr,
                                        (num_assignment*self.num_species, self.num_reaction))
            # Compare each row
            big_compatible_arr = np.equal(big_reference_arr, big_target_arr)
            big_row_sum = np.sum(big_compatible_arr, axis=1)
            big_row_satisfy = big_row_sum == self.num_reaction
            # Rows are results of the comparison of the reference and target; columns are assignments
            assignment_pair_satisfy_arr = np.reshape(big_row_satisfy, (num_assignment, self.num_species))
            # Index is True if the assignment-pair results in an identical matrix
            assignment_satisfy_arr = np.sum(assignment_pair_satisfy_arr, axis=1) == target.num_species
            return assignment_satisfy_arr  # Booleans indicating acceptable assignments
        #
        # Analyze by identity
        if identity == cn.ID_WEAK:
            assignment_pair_arr = compare(participant=None)
        else:
            # Strong identity requires that both reactant and product satisfy the assignment
            assignment_pair_arr = compare(participant=cn.PR_REACTANT) & compare(participant=cn.PR_PRODUCT)
        # Construct the assignment pairs
        assignment_idxs = np.array(range(len(assignment_pair_arr)))
        num_reaction_assignment = reaction_assignment_arr.shape[0]
        species_idxs = assignment_idxs//num_reaction_assignment
        reaction_idxs = np.mod(assignment_idxs, num_reaction_assignment)
        assignment_pairs = []
        for species_idx, reaction_idx in zip(species_idxs, reaction_idxs):
            species_assignment = species_assignment_arr[species_idx, :]
            reaction_assignment = reaction_assignment_arr[reaction_idx, :]
            assignment_pair = AssignmentPair(species_assignment=species_assignment,
                                            reaction_assignment=reaction_assignment)
            assignment_pairs.append(assignment_pair)
        # Construct the result
        return StructurallyIdenticalResult(assignment_pairs=assignment_pairs,
                is_truncated=is_trucated,
                species_compression_factor=species_assignment_result.compression_factor,
                reaction_compression_factor=reaction_assignment_result.compression_factor)