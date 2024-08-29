'''Efficient container of properties for a reaction network.'''

from sirn import constants as cn  # type: ignore
from sirn.criteria_vector import CriteriaVector  # type: ignore
from sirn.matrix import Matrix  # type: ignore
from sirn.named_matrix import NamedMatrix  # type: ignore
from sirn.pair_criteria_count_matrix import PairCriteriaCountMatrix  # type: ignore
from sirn.single_criteria_count_matrix import SingleCriteriaCountMatrix  # type: ignore
from sirn.stoichometry import Stoichiometry  # type: ignore
from sirn import util  # type: ignore
import sirn.constants as cn # type: ignore

import collections
import itertools
import os
import pandas as pd  # type: ignore
import numpy as np
from typing import Optional, Tuple


AssignmentPair = collections.namedtuple('AssignmentPair', 'species_assignment reaction_assignment')

CRITERIA_VECTOR = CriteriaVector()


class NetworkBase(object):
    """
    Abstraction for a reaction network. This is represented by reactant and product stoichiometry matrices.
    """

    def __init__(self, reactant_arr:Matrix, 
                 product_arr:np.ndarray,
                 reaction_names:Optional[np.ndarray[str]]=None,
                 species_names:Optional[np.ndarray[str]]=None,
                 network_name:Optional[str]=None,
                 criteria_vector:CriteriaVector=CRITERIA_VECTOR)->None:
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
        self.criteria_vector = criteria_vector
        self.reactant_mat = NamedMatrix(reactant_arr, row_names=species_names, column_names=reaction_names,
              row_description="species", column_description="reactions")
        self.product_mat = NamedMatrix(product_arr, row_names=species_names, column_names=reaction_names,
              row_description="species", column_description="reactions")
        self.standard_mat = NamedMatrix(product_arr - reactant_arr, row_names=species_names,
              column_names=reaction_names, row_description="species", column_description="reactions")
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
    def weak_hash(self):
        if self._weak_hash is None:
            single_criteria_matrices = [self.getNetworkMatrix(
                                  matrix_type=cn.MT_SINGLE_CRITERIA, orientation=o,
                                  identity=cn.ID_WEAK)
                                  for o in [cn.OR_SPECIES, cn.OR_REACTION]]
            # Maintain the order of species and reactions
            hash_arr = np.sort([s.row_order_independent_hash for s in single_criteria_matrices])
            self._weak_hash = util.makeRowOrderIndependentHash(hash_arr)
        return self._weak_hash
        
    @property
    def strong_hash(self):
        if self._strong_hash is None:
            orientations = [cn.OR_SPECIES, cn.OR_REACTION]
            participants = [cn.PR_REACTANT, cn.PR_PRODUCT]
            combinations = itertools.product(orientations, participants)
            single_criteria_matrices = [self.getNetworkMatrix(
                  matrix_type=cn.MT_SINGLE_CRITERIA, orientation=o, identity=cn.ID_STRONG, participant=p)
                  for o, p in combinations]
            hash_arr = np.sort([s.row_order_independent_hash for s in single_criteria_matrices])
            self._strong_hash = util.makeRowOrderIndependentHash(hash_arr)
        return self._strong_hash
        
    @property
    def deprecated_strong_hash(self)->int:
        if self._strong_hash is None:
            stoichiometries:list = []
            for i_orientation in cn.OR_LST:
                for i_participant in cn.PR_LST:
                    stoichiometries.append(self.getNetworkMatrix(
                        matrix_type=cn.MT_SINGLE_CRITERIA,
                        orientation=i_orientation,
                        identity=cn.ID_STRONG,
                        participant=i_participant))
            #hash_arr = np.array([hashArray(stoichiometry.row_hashes.values) for stoichiometry in stoichiometries])
            #hash_arr = np.sort(hash_arr)
            #self._strong_hash = hashArray(hash_arr)
            self._strong_hash = hash(str(stoichiometries))
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
            marix_type: cn.MT_STOICHIOMETRY, cn.MT_SINGLE_CRITERIA, cn.MT_PAIR_CRITERIA
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
            matrix = SingleCriteriaCountMatrix(matrix.values, criteria_vector=self.criteria_vector)
        elif matrix_type == cn.MT_PAIR_CRITERIA:
            matrix = PairCriteriaCountMatrix(matrix.values, criteria_vector=self.criteria_vector)
        elif matrix_type == cn.MT_STOICHIOMETRY:
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
                       criteria_vector=self.criteria_vector)  # type: ignore

    def __repr__(self)->str:
        repr = f"{self.network_name}: {self.num_species} species, {self.num_reaction} reactions"
        reactions = ["  " + self.prettyPrintReaction(i) for i in range(self.num_reaction)]
        repr += '\n' + '\n'.join(reactions)
        return repr
    
    def isMatrixEqual(self, other, identity:str=cn.ID_WEAK)->bool:
        """
        Check if the stoichiometry matrix is equal to another network's matrix.
            weak identity: standard stoichiometry matrix 
            strong identity: reactant and product matrices

        Args:
            other (_type_): Network
            identity (str, optional): Defaults to cn.ID_WEAK.

        Returns:
            bool
        """
        def check(matrix_type, identity, participant=None):
            matrix1 = self.getNetworkMatrix(matrix_type=matrix_type, orientation=cn.OR_SPECIES,
                participant=participant, identity=identity)
            matrix2 = other.getNetworkMatrix(matrix_type=matrix_type, orientation=cn.OR_SPECIES,
                participant=participant, identity=identity)
            return np.all(matrix1.values == matrix2.values)
        #
        if identity == cn.ID_WEAK:
            if not check(cn.MT_STOICHIOMETRY, identity):
                return False
        else:
            if not check(cn.MT_STOICHIOMETRY, identity, participant=cn.PR_REACTANT):
                return False
            if not check(cn.MT_STOICHIOMETRY, identity, participant=cn.PR_PRODUCT):
                return False
        return True
    
    def __eq__(self, other)->bool:
        if not self.isMatrixEqual(other, identity=cn.ID_STRONG):
            return False
        if self.network_name != other.network_name:
            return False
        if not np.all(self.species_names == other.species_names):
            return False
        if not np.all(self.reaction_names == other.reaction_names):
            return False
        return True
    
    def permute(self, assignment_pair:Optional[AssignmentPair]=None)->Tuple['NetworkBase', AssignmentPair]:
        """
        Creates a new network with permuted reactant and product matrices. If no permutation is specified,
        then a random permutation is used.

        Returns:
            BaseNetwork (class of caller)
            AssignmentPair (species_assignment, reaction_assignment) for reconstructing the original network.
        """
        if assignment_pair is None:
            reaction_perm = np.random.permutation(range(self.num_reaction))
            species_perm = np.random.permutation(range(self.num_species))
        else:
            reaction_perm = assignment_pair.reaction_assignment
            species_perm = assignment_pair.species_assignment
        reactant_arr = self.reactant_mat.values.copy()
        product_arr = self.product_mat.values.copy()
        reactant_arr = reactant_arr[species_perm, :]
        reactant_arr = reactant_arr[:, reaction_perm]
        product_arr = product_arr[species_perm, :]
        product_arr = product_arr[:, reaction_perm]
        reaction_names = np.array([self.reaction_names[i] for i in reaction_perm])
        species_names = np.array([self.species_names[i] for i in species_perm])
        assignment_pair = AssignmentPair(np.argsort(species_perm), np.argsort(reaction_perm))
        return self.__class__(reactant_arr, product_arr, network_name=self.network_name,
              reaction_names=reaction_names, species_names=species_names), assignment_pair
    
    def isStructurallyCompatible(self, other:'NetworkBase', identity:str=cn.ID_WEAK)->bool:
        """
        Determines if two networks are compatible to be structurally identical.
        This means that they have the same species and reactions.

        Args:
            other (Network): Network to compare to.
            identity (str): cn.ID_WEAK or cn.ID_STRONG

        Returns:
            bool: True if compatible.
        """
        if self.num_species != other.num_species:
            return False
        if self.num_reaction != other.num_reaction:
            return False
        is_identity = self.weak_hash == other.weak_hash
        if identity == cn.ID_STRONG:
            is_identity = self.strong_hash == other.strong_hash
        return bool(is_identity)

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
        reactant_mat = np.random.randint(0, 3, (species_array_size, reaction_array_size))
        product_mat = np.random.randint(0, 3, (species_array_size, reaction_array_size))
        return cls(reactant_mat, product_mat)
    
    @classmethod
    def makeRandomNetworkByReactionType(cls, num_reaction:int, num_species:Optional[int]=None,
          input_boundary_frac:Optional[float]=0.1, output_boundary_frac:Optional[float]=0.14,
          uni_uni_frac:Optional[float]=0.34, uni_bi_frac:Optional[float]=0.13, bi_uni_frac:Optional[float]=0.19,
          bi_bi_frac:Optional[float]=0.07)->'NetworkBase':
        """
        Makes a random network based on the type of reaction: input_boundary, output_boundary,
            uni_uni, uni_bi, bi_uni, bi_bi.
        Fractions are from the paper "SBMLKinetics: a tool for annotation-independent classification of
            reaction kinetics for SBML models", Jin Liu, BMC Bioinformatics, 2023.

        Args:
            num_reaction (int): Number of reactions.
            num_species (int): Number of species.
            input_boundary_frac (float): Fraction of input boundary reactions.
            output_boundary_frac (float): Fraction of output boundary reactions.
            uni_uni_frac (float): Fraction of uni-uni reactions.
            uni_bi_frac (float): Fraction of uni-bi reactions.
            bi_bi_frac (float): Fraction of bi-bi reactions.

        Returns:
            Network
        """
        SUFFIX = "_frac"
        # Handle defaults
        if num_species is None:
            num_species = num_reaction
        # Initializations
        REACTION_TYPES = ['input_boundary', 'output_boundary', 'uni_uni', 'uni_bi', 'bi_uni', 'bi_bi']
        FRAC_NAMES = [n + SUFFIX for n in REACTION_TYPES]
        value_dct:dict = {}
        total = np.sum([input_boundary_frac, output_boundary_frac, uni_uni_frac, uni_bi_frac, bi_uni_frac, bi_bi_frac])
        for name in FRAC_NAMES:
            value = locals()[name]
            value_dct[name] = value/total
        CULMULATIVE_ARR = np.cumsum([value_dct[n + SUFFIX] for n in REACTION_TYPES])
        #######
        def getType(frac:float)->str:
            """
            Returns the name of the reaction associated with the fraction (e.g., a random (0, 1))

            Args:
                frac (float)

            Returns:
                str: Reaction type
            """
            pos = np.sum(CULMULATIVE_ARR < frac)
            reaction_type = REACTION_TYPES[pos]
            return reaction_type
        #######
        # Initialize the reactant and product matrices
        reactant_arr = np.zeros((num_species, num_reaction))
        product_arr = np.zeros((num_species, num_reaction))
        # Construct the reactions
        for i_reaction in range(num_reaction):
            frac = np.random.rand()
            reaction_type = getType(frac)
            if reaction_type == 'input_boundary':
                i_species = np.random.randint(0, num_species)
                product_arr[i_species, i_reaction] = 1
            elif reaction_type == 'output_boundary':
                i_species = np.random.randint(0, num_species)
                reactant_arr[i_species, i_reaction] = 1
            elif reaction_type == 'uni_uni':
                i_species1 = np.random.randint(0, num_species)
                i_species2 = np.random.randint(0, num_species)
                reactant_arr[i_species1, i_reaction] = 1
                product_arr[i_species2, i_reaction] = 1
            elif reaction_type == 'uni_bi':
                i_species1 = np.random.randint(0, num_species)
                i_species2 = np.random.randint(0, num_species)
                i_species3 = np.random.randint(0, num_species)
                reactant_arr[i_species1, i_reaction] = 1
                product_arr[i_species2, i_reaction] = 1
                product_arr[i_species3, i_reaction] = 1
            elif reaction_type == 'bi_uni':
                i_species1 = np.random.randint(0, num_species)
                i_species2 = np.random.randint(0, num_species)
                i_species3 = np.random.randint(0, num_species)
                reactant_arr[i_species1, i_reaction] = 1
                reactant_arr[i_species2, i_reaction] = 1
                product_arr[i_species3, i_reaction] = 1
            else:
                i_species1 = np.random.randint(0, num_species)
                i_species2 = np.random.randint(0, num_species)
                i_species3 = np.random.randint(0, num_species)
                i_species4 = np.random.randint(0, num_species)
                reactant_arr[i_species1, i_reaction] = 1
                reactant_arr[i_species2, i_reaction] = 1
                product_arr[i_species3, i_reaction] = 1
                product_arr[i_species4, i_reaction] = 1
        # Eliminate 0 rows (species not used)
        keep_idxs:list = []
        for i_species in range(num_species):
            if np.sum(reactant_arr[i_species, :]) > 0 or np.sum(product_arr[i_species, :]) > 0:
                keep_idxs.append(i_species)
        reactant_arr = reactant_arr[keep_idxs, :]
        product_arr = product_arr[keep_idxs, :]
        # Construct the network
        network = cls(reactant_arr, product_arr)
        return network
   
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

    def makeNetworkFromAssignmentPair(self, assignment_pair:AssignmentPair)->'NetworkBase':
        """
        Constructs a network from an assignment pair.

        Args:
            assignment_pair (AssignmentPair): Assignment pair.

        Returns:
            Network: Network constructed from the assignment pair.
        """
        species_assignment = assignment_pair.species_assignment
        reaction_assignment = assignment_pair.reaction_assignment
        reactant_arr = self.reactant_mat.values[species_assignment, :]
        product_arr = self.product_mat.values[species_assignment, :]
        reactant_arr = reactant_arr[:, reaction_assignment]
        product_arr = product_arr[:, reaction_assignment]
        return NetworkBase(reactant_arr, product_arr, reaction_names=self.reaction_names[reaction_assignment],
                        species_names=self.species_names[species_assignment])
    
    def serialize(self):
        """
        Serialize the network.

        Returns:
            Series: See SERIALIZATION_NAMES
        """
        reactant_array_context = util.array2Context(self.reactant_mat.values)
        product_array_context = util.array2Context(self.product_mat.values)
        criteria_serialization = self.criteria_vector.serialize()
        dct = {cn.NETWORK_NAME: self.network_name,
               cn.NUM_SPECIES: self.num_species,
               cn.NUM_REACTION: self.num_reaction,
               cn.REACTANT_ARRAY_STR: reactant_array_context.string,
               cn.PRODUCT_ARRAY_STR: product_array_context.string,
               cn.REACTION_NAMES: self.reaction_names.tolist(),
               cn.SPECIES_NAMES: self.species_names.tolist(),
               cn.CRITERIA_ARRAY_STR: criteria_serialization.string,
               cn.CRITERIA_ARRAY_LEN: criteria_serialization.num_column,
               }
        return pd.Series(dct)
    
    @classmethod
    def deserialize(cls, ser:pd.Series):
        """
        Deserialize the network.

        Args:
            ser (Series): Serialized network.

        Returns:
            Network
        """
        reactant_array_context = util.ArrayContext(ser[cn.REACTANT_ARRAY_STR], ser[cn.NUM_SPECIES],
              ser[cn.NUM_REACTION])
        product_array_context = util.ArrayContext(ser[cn.PRODUCT_ARRAY_STR], ser[cn.NUM_SPECIES],
              ser[cn.NUM_REACTION])
        reactant_arr = util.string2Array(reactant_array_context)
        product_arr = util.string2Array(product_array_context)
        boundary_array_context = util.ArrayContext(ser[cn.CRITERIA_ARRAY_STR], 1,
              ser[cn.CRITERIA_ARRAY_LEN])
        boundary_arr = util.string2Array(boundary_array_context).flatten()
        criteria_vector = CriteriaVector(boundary_arr)
        return cls(reactant_arr, product_arr, network_name=ser[cn.NETWORK_NAME],
                       reaction_names=np.array(ser[cn.REACTION_NAMES]),
                       species_names=np.array(ser[cn.SPECIES_NAMES]),
                       criteria_vector=criteria_vector)