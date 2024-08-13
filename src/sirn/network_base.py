'''Efficient container of properties for a reaction network.'''

from sirn import constants as cn  # type: ignore
from sirn.criteria_vector import CriteriaVector  # type: ignore
from sirn.matrix import Matrix  # type: ignore
from sirn.named_matrix import NamedMatrix  # type: ignore
from sirn.pair_criteria_count_matrix import PairCriteriaCountMatrix  # type: ignore
from sirn.single_criteria_count_matrix import SingleCriteriaCountMatrix  # type: ignore
from sirn.stoichometry import Stoichiometry  # type: ignore
from sirn.util import hashArray  # type: ignore

import os
import numpy as np
from typing import Optional


class NetworkBase(object):
    """
    Abstraction for a reaction network. This is represented by reactant and product stoichiometry matrices.
    """

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
        # Reactant stoichiometry matrix is negative
        if not np.all(reactant_arr.shape == product_arr.shape):
            raise ValueError("Reactant and product matrices must have the same shape.")
        self.num_species, self.num_reaction = np.shape(reactant_arr)
        self.criteria_vec = criteria_vector
        self.reactant_mat = NamedMatrix(reactant_arr, row_names=species_names, column_names=reaction_names,
                                        row_description="species", column_description="reactions")
        self.product_mat = NamedMatrix(product_arr, row_names=species_names, column_names=reaction_names,
                                        row_description="species", column_description="reactions")
        # The following are deferred execution for efficiency considerations
        self._species_names = species_names
        self._reaction_names = reaction_names
        self._network_name = network_name
        self._stoichiometry_mat:Optional[NamedMatrix] = None
        self._network_mats:Optional[dict] = None # Network matrices populated on demand by getNetworkMat
        self._strong_hash:Optional[int] = None  # Hash for strong identity
        self._weak_hash:Optional[int] = None  # Hash for weak identity

    # Properties for handling deferred execution
    @property
    def species_names(self)->np.ndarray[str]:
        if self._species_names is None:
            self._species_names = np.array([f"S{i}" for i in range(self.num_species)])
        if not isinstance(self._species_names, np.ndarray):
            self._species_names = np.array(self._species_names)
        return self._species_names
    
    @property
    def reaction_names(self)->np.ndarray[str]:
        if self._reaction_names is None:
            self._reaction_names = np.array([f"J{i}" for i in range(self.num_reaction)])
        if not isinstance(self._reaction_names, np.ndarray):
            self._reaction_names = np.array(self._reaction_names)
        return self._reaction_names

    @property
    def weak_hash(self)->int:
        if self._weak_hash is None:
            stoichiometries = [self.getNetworkMatrix(
                                  matrix_type=cn.MT_SINGLE_CRITERIA, orientation=o,
                                  identity=cn.ID_WEAK)
                                  for o in [cn.OR_SPECIES, cn.OR_REACTION]]
            hash_arr = np.array([hashArray(stoichiometry.row_hashes) for stoichiometry in stoichiometries])
            hash_arr = np.sort(hash_arr)
            self._weak_hash = hashArray(hash_arr)
        return self._weak_hash
        
    @property
    def strong_hash(self)->int:
        if self._strong_hash is None:
            stoichiometries:list = []
            for i_orientation in cn.OR_LST:
                for i_participant in cn.PR_LST:
                    stoichiometries.append(self.getNetworkMatrix(
                        matrix_type=cn.MT_SINGLE_CRITERIA,
                        orientation=i_orientation,
                        identity=cn.ID_STRONG,
                        participant=i_participant))
            hash_arr = np.array([hashArray(stoichiometry.row_hashes) for stoichiometry in stoichiometries])
            hash_arr = np.sort(hash_arr)
            self._strong_hash = hashArray(hash_arr)
        return self._strong_hash

    @property
    def network_name(self)->str:
        if self._network_name is None:
            self._network_name = str(np.random.randint(0, 10000000))
        return self._network_name
    
    @property
    def stoichiometry_mat(self)->NamedMatrix:
        if self._stoichiometry_mat is None:
            stoichiometry_arr = self.product_mat.values - self.reactant_mat.values
            self._stoichiometry_mat = NamedMatrix(stoichiometry_arr, row_names=self.species_names,
               column_names=self.reaction_names, row_description="species", column_description="reactions")
        return self._stoichiometry_mat

    # Methods 
    def getNetworkMatrix(self,
                         matrix_type:Optional[str]=None,
                         orientation:Optional[str]=None,
                         participant:Optional[str]=None,
                         identity:Optional[str]=None)->NamedMatrix:
        """
        Retrieves, possibly constructing, the matrix. The specific matrix is determined by the arguments.

        Args:
            marix_type: cn.MT_STANDARD, cn.MT_SINGLE_CRITERIA, cn.MT_PAIR_CRITERIA
            orientation: cn.OR_REACTION, cn.OR_SPECIES
            participant: cn.PR_REACTANT, cn.PR_PRODUCT
            identity: cn.ID_WEAK, cn.ID_STRONG

        Returns:
            subclass of Matrix
        """
        # Initialize the dictionary of matrices
        if self._network_mats is None:
            self._network_mats = {}
            for i_matrix_type in cn.MT_LST:
                for i_orientation in cn.OR_LST:
                    for i_identity in cn.ID_LST:
                        for i_participant in cn.PR_LST:
                            if i_identity == cn.ID_WEAK:
                                self._network_mats[(i_matrix_type, i_orientation, None, i_identity)] = None
                            else:
                                self._network_mats[(i_matrix_type, i_orientation, i_participant, i_identity)] = None
        # Check if the matrix is already in the dictionary
        if self._network_mats[(matrix_type, orientation, participant, identity)] is not None:
            return self._network_mats[(matrix_type, orientation, participant, identity)]
        # Obtain the matrix value
        #   Identity and participant
        if identity == cn.ID_WEAK:
            matrix = self.stoichiometry_mat
        elif identity == cn.ID_STRONG:
            if participant == cn.PR_REACTANT:
                matrix = self.reactant_mat
            elif participant == cn.PR_PRODUCT:
                matrix = self.product_mat
            else:
                raise ValueError("Invalid participant: {participant}.")
        else:
            raise ValueError("Invalid identity: {identity}.")
        #   Orientation
        if orientation == cn.OR_REACTION:
            matrix = matrix.transpose()
        elif orientation == cn.OR_SPECIES:
            pass
        else:
            raise ValueError("Invalid orientation: {orientation}.")
        #   Matrix type
        if matrix_type == cn.MT_SINGLE_CRITERIA:
            matrix = SingleCriteriaCountMatrix(matrix.values, criteria_vector=self.criteria_vec)
        elif matrix_type == cn.MT_PAIR_CRITERIA:
            matrix = PairCriteriaCountMatrix(matrix.values, criteria_vector=self.criteria_vec)
        elif matrix_type == cn.MT_STANDARD:
            pass
        else:
            raise ValueError("Invalid matrix type: {matrix_type}.")
        # Update the matrix
        self._network_mats[(matrix_type, orientation, participant, identity)] = matrix
        return matrix

    def copy(self)->'NetworkBase':
        return NetworkBase(self.reactant_mat.values.copy(), self.product_mat.values.copy(),
                       network_name=self.network_name, reaction_names=self.reaction_names,
                       species_names=self.species_names,
                       criteria_vector=self.criteria_vec)  # type: ignore

    def __repr__(self)->str:
        repr = f"{self.network_name}: {self.num_species} species, {self.num_reaction} reactions"
        reactions = ["  " + self.prettyPrintReaction(i) for i in range(self.num_reaction)]
        repr += '\n' + '\n'.join(reactions)
        return repr
    
    def __eq__(self, other)->bool:
        if self.network_name != other.network_name:
            return False
        if self.reactant_mat != other.reactant_mat:
            return False
        if self.product_mat != other.product_mat:
            return False
        return True
    
    def randomlyPermute(self)->'NetworkBase':
        """
        Creates a new network with permuted reactant and product matrices using the same random permutation.

        Returns:
            BaseNetwork
        """
        reaction_perm = np.random.permutation(range(self.num_reaction))
        species_perm = np.random.permutation(range(self.num_species))
        reactant_arr = self.reactant_mat.values[species_perm, :]
        reactant_arr = reactant_arr[:, reaction_perm]
        product_arr = self.product_mat.values[species_perm, :]
        product_arr = product_arr[:, reaction_perm]
        reaction_names = np.array([self.reaction_names[i] for i in reaction_perm])
        species_names = np.array([self.species_names[i] for i in species_perm])
        return NetworkBase(reactant_arr, product_arr, network_name=self.network_name,
              reaction_names=reaction_names, species_names=species_names)
    
    def isStructurallyCompatible(self, other:'NetworkBase')->bool:
        """
        Determines if two networks are compatible to be structurally identical.
        This means that they have the same species and reactions.

        Args:
            other (Network): Network to compare to.

        Returns:
            bool: True if compatible.
        """
        if self.num_species != other.num_species:
            return False
        if self.num_reaction != other.num_reaction:
            return False
        if not (self.weak_hash == other.weak_hash) or not (self.strong_hash == other.strong_hash):
            return False
        return True

    # FIXME: More sophisticated subset checking? 
    def isSubsetCompatible(self, other:'NetworkBase')->bool:
        """
        Determines if two networks are compatible in that self can be a subset of other.
        This means that they have the same species and reactions.

        Args:
            other (Network): Network to compare to.

        Returns:
            bool: True if compatible.
        """
        if self.num_species > other.num_species:
            return False
        if self.num_reaction > other.num_reaction:
            return False
        return True
    
    @classmethod
    def makeFromAntimonyStr(cls, antimony_str:str, network_name:Optional[str]=None)->'NetworkBase':
        """
        Make a Network from an Antimony string.

        Args:
            antimony_str (str): Antimony string.
            network_name (str): Name of the network.

        Returns:
            Network
        """
        stoichiometry = Stoichiometry(antimony_str)
        network = cls(stoichiometry.reactant_mat, stoichiometry.product_mat, network_name=network_name,
                      species_names=stoichiometry.species_names, reaction_names=stoichiometry.reaction_names)
        return network
                   
    @classmethod
    def makeFromAntimonyFile(cls, antimony_path:str,
                         network_name:Optional[str]=None)->'NetworkBase':
        """
        Make a Network from an Antimony file. The default network name is the file name.

        Args:
            antimony_path (str): path to an Antimony file.
            network_name (str): Name of the network.

        Returns:
            Network
        """
        with open(antimony_path, 'r') as fd:
            antimony_str = fd.read()
        if network_name is None:
            filename = os.path.basename(antimony_path)
            network_name = filename.split('.')[0]
        return cls.makeFromAntimonyStr(antimony_str, network_name=network_name)
    
    @classmethod
    def makeRandomNetwork(cls, species_array_size:int=5, reaction_array_size:int=5)->'NetworkBase':
        """
        Makes a random network.

        Args:
            species_array_size (int): Number of species.
            reaction_array_size (int): Number of reactions.

        Returns:
            Network
        """
        reactant_mat = np.random.randint(-1, 2, (species_array_size, reaction_array_size))
        product_mat = np.random.randint(-1, 2, (species_array_size, reaction_array_size))
        return NetworkBase(reactant_mat, product_mat)
   
    def prettyPrintReaction(self, index:int)->str:
        """
        Pretty prints a reaction.

        Args:
            index (int): Index of the reaction.

        Returns:
            str
        """
        def makeSpeciesExpression(reaction_idx:int, stoichiometry_mat:np.ndarray)->str:
            all_idxs = np.array(range(self.num_species))
            species_idxs = all_idxs[stoichiometry_mat[:, reaction_idx] > 0]
            species_names = self.species_names[species_idxs]
            stoichiometries = [s for s in stoichiometry_mat[species_idxs, reaction_idx]]
            stoichiometries = ["" if np.isclose(s, 1) else str(s) + " " for s in stoichiometries]
            expressions = [f"{stoichiometries[i]}{species_names[i]}" for i in range(len(species_names))]
            result =  ' + '.join(expressions)
            return result
        #
        reactant_expression = makeSpeciesExpression(index, self.reactant_mat.values)
        product_expression = makeSpeciesExpression(index, self.product_mat.values)
        result = f"{self.reaction_names[index]}: " + f"{reactant_expression} -> {product_expression}"
        return result