"""
Dynamical Models
================

Core dynamics objects are defined here:

.. autosummary::
   VarGroup
   AbstractDynamicsModel


Implementations
---------------

Several dynamical models are implemented in submodules.

.. toctree::
   :maxdepth: 1

   dynamics.crtbp
   dynamics.lowthrust

Module Reference
-----------------

.. autoclass:: VarGroup
   :members:
   :show-inheritance:

.. autoclass:: AbstractDynamicsModel
   :members:

"""
import logging
from abc import ABC, abstractmethod
from copy import copy, deepcopy
from enum import IntEnum

import numpy as np

from medusa import util
from medusa.data import Body

logger = logging.getLogger(__name__)

__all__ = [
    # base module
    "VarGroup",
    "AbstractDynamicsModel",
    "ModelBlockCopyMixin",
    # sub modules
    "crtbp",
    "lowthrust",
]


# numba JIT compilation only supports Enum and IntEnum
class VarGroup(IntEnum):
    """
    Specify the variable groups included in a model variable array. The integer
    values of the groups correspond to their location in a variable array. I.e.,
    the ``STATE`` variables are always first, followed by the ``STM``,
    ``EPOCH_PARTIALS``, and ``PARAM_PARTIALS``. All matrix objects are stored in
    row-major order within the variable vector.
    """

    STATE = 0
    """
    State variables; usually includes the position and velocity coordinates
    """

    STM = 1
    """ 
    State Transition Matrix; An N**2 matrix of the time-evolving partial derivatives
    of the propagated state w.r.t. the initial state, where N is the size of the
    ``STATE`` component
    """

    EPOCH_PARTIALS = 2
    """
    Epoch partials; An N-element vector of the time-evolving partial derivatives
    of the propagated state w.r.t. the initial epoch where N is the size of the
    ``STATE`` component
    """

    PARAM_PARTIALS = 3
    """
    Parameter partials; An NxM matrix of the time-evolving partial derivatives
    of the propagated state w.r.t. the parameter values where N is the size of
    the ``STATE`` component and ``M`` is the number of parameters.

    Parameters are constant through an integration, i.e., they do not have their
    own governing differential equations. Parameters can include thrust magnitude,
    solar pressure coefficients, etc.
    """


class AbstractDynamicsModel(ABC):
    """
    Contains the mathematics that define a dynamical model

    Args:
        bodies ([Body]): one or more primary bodies
        properties: keyword arguments that define model properties

    Attributes:
        bodies (tuple): a tuple of :class:`~medusa.data.Body` objects
        properties (dict): the model properties; these are constant across all
            integrations; e.g., a mass ratio for the CR3BP, or the initial phasing
            of multiple bodies in a four-body problem.
        charL (float): a characteristic length (km) used to nondimensionalize lengths
        charT (float): a characteristic time (sec) used to nondimensionalize times
        charM (float): a characteristic mass (kg) used to nondimensionalize masses
    """

    def __init__(self, *bodies, **properties):
        if any([not isinstance(body, Body) for body in bodies]):
            raise TypeError("Expecting Body objects")

        # Copy body objects into tuple
        self.bodies = tuple(copy(body) for body in bodies)

        # Unpack parameters into internal dict
        self._properties = {**properties}

        # Define default characteristic quantities as unity
        self._charL = 1.0  # km
        self._charT = 1.0  # sec
        self._charM = 1.0  # kg

    @property
    def properties(self):
        return copy(self._properties)

    @property
    def charL(self):
        return self._charL

    @property
    def charT(self):
        return self._charT

    @property
    def charM(self):
        return self._charM

    def __eq__(self, other):
        """
        Compare two Model objects. This can be overridden for more specific
        comparisons in derived classes
        """
        if not isinstance(other, AbstractDynamicsModel):
            return False

        if not type(self) == type(other):
            return False

        if not all([b1 == b2 for b1, b2 in zip(self.bodies, other.bodies)]):
            return False

        # TODO need to compare dicts by value??
        return (
            self.properties == other.properties
            and self.charL == other.charL
            and self.charT == other.charT
            and self.charM == other.charM
        )

    @abstractmethod
    def bodyState(self, ix, t, params):
        """
        Evaluate a body state vector at a time

        Args:
            ix (int): index of the body within :attr:`bodies`
            t (float): time value
            params (float, [float]): one or more parameter values

        Returns:
            numpy.ndarray: state vector for the body
        """
        pass

    @abstractmethod
    def diffEqs(self, t, y, varGroups, params):
        """
        Evaluate the differential equations that govern the variable array

        Args:
            t (float): independent variable (e.g., time)
            y (numpy.ndarray<float>): One-dimensional variable array
            varGroups (tuple of VarGroup): describes the variable groups included
                in the ``y`` vector
            params (float, [float]): one or more parameter values. These are
                generally constants that may vary integration to integration
                within a model (e.g., thrust magnitude) but are not constants
                of the model itself (e.g., mass ratio).

        Returns:
            numpy.ndarray: the derivative of the ``y`` vector with respect to ``t``
        """
        pass

    @property
    @abstractmethod
    def epochIndependent(self):
        """
        Returns:
            bool: True if the dynamics model has no dependencies on epoch, False
            otherwise.
        """
        pass

    @abstractmethod
    def stateSize(self, varGroups):
        """
        Get the size (i.e., number of elements) for one or more variable groups.

        Args:
            varGroups (VarGroup, [VarGroup]): describes one or more groups of variables

        Returns:
            int: the size of a variable array with the specified variable groups
        """
        pass

    def checkPartials(
        self,
        y0,
        tspan,
        params=None,
        initStep=1e-4,
        rtol=1e-6,
        atol=1e-8,
        printTable=True,
    ):
        """
        Check the partial derivatives included in the equations of motion

        Args:
            y0 (numpy.ndarray): afull state vector (includes all VarGroups) for
                this model
            tspan ([float]): a 2-element vector defining the start and end times
                for numerical propagation
            params (Optional, [float]): propagation parameters
            initStep (Optional, float): the initial step size for the multivariate
                numerical derivative function in :func:`numerics.derivative_multivar`
            rtol (Optional, float): the numeric and analytical values are
                equal when the absolute value of (numeric - analytic)/numeric
                is less than ``rtol``
            atol (Optional, float): the numeric and analytic values are equal
                when the absolute value of (numeric - analytic) is less than ``atol``
            printTable (Optional, bool): whether or not to print a table of the
                partial derivatives, their expected (numeric) and actual (analytic)
                values, and the relative and absolute errors between the expected
                and actual values.

        Returns:
            bool: True if each partial derivative satisfies the relative *or*
            absolute tolerance; False is returned if any of the partials fail
            both tolerances.
        """
        from rich.table import Table

        from medusa import console, numerics
        from medusa.propagate import Propagator

        allVars = [
            VarGroup.STATE,
            VarGroup.STM,
            VarGroup.EPOCH_PARTIALS,
            VarGroup.PARAM_PARTIALS,
        ]

        if not len(y0) == self.stateSize(allVars):
            raise ValueError(
                "y0 must define the full vector (STATE + STM + EPOCH_PARTIALS + PARAM_PARTIALS"
            )

        # TODO ensure tolerances are tight enough?
        prop = Propagator(self, dense=False)
        state0 = self.extractVars(y0, VarGroup.STATE, VarGroupIn=allVars)

        solution = prop.propagate(y0, tspan, params=params, VarGroup=allVars)
        sol_vec = np.concatenate(
            [
                self.extractVars(solution.y[:, -1], grp, VarGroupIn=allVars).flatten()
                for grp in allVars[1:]
            ]
        )

        # Compute state partials (STM)
        def prop_state(y):
            sol = prop.propagate(y, tspan, params=params, VarGroup=VarGroup.STATE)
            return sol.y[:, -1]

        num_stm = numerics.derivative_multivar(prop_state, state0, initStep)

        # Compute epoch partials
        if self.stateSize(VarGroup.EPOCH_PARTIALS) > 0:

            def prop_epoch(epoch):
                sol = prop.propagate(
                    state0,
                    [epoch + t for t in tspan],
                    params=params,
                    VarGroup=VarGroup.STATE,
                )
                return sol.y[:, -1]

            num_epochPartials = numerics.derivative_multivar(
                prop_epoch, tspan[0], initStep
            )
        else:
            num_epochPartials = np.array([])

        # Compute parameter partials
        if self.stateSize(VarGroup.PARAM_PARTIALS) > 0:

            def prop_params(p):
                sol = prop.propagate(state0, tspan, params=p, VarGroup=VarGroup.STATE)
                return sol.y[:, -1]

            num_paramPartials = numerics.derivative_multivar(
                prop_params, params, initStep
            )
        else:
            num_paramPartials = np.array([])

        # Combine into flat vector
        num_vec = np.concatenate(
            (
                num_stm.flatten(),
                num_epochPartials.flatten(),
                num_paramPartials.flatten(),
            )
        )

        # Now compare
        absDiff = abs(num_vec - sol_vec)
        relDiff = absDiff.copy()
        equal = True
        varNames = np.concatenate([self.varNames(grp) for grp in allVars[1:]])
        table = Table(
            "Status",
            "Name",
            "Expected",
            "Actual",
            "Rel Err",
            "Abs Err",
            title="Partial Derivative Check",
        )

        for ix in range(sol_vec.size):
            # Compute relative difference for non-zero numeric values
            if abs(num_vec[ix]) > 1e-12:
                relDiff[ix] = absDiff[ix] / abs(num_vec[ix])

            relOk = abs(relDiff[ix]) <= rtol
            rStyle = "i" if relOk else "u"
            absOk = abs(absDiff[ix]) <= atol
            aStyle = "i" if absOk else "u"

            table.add_row(
                "OK" if relOk or absOk else "ERR",
                varNames[ix],
                f"{num_vec[ix]:.4e}",
                f"{sol_vec[ix]:.4e}",
                f"[{rStyle}]{relDiff[ix]:.4e}[/{rStyle}]",
                f"[{aStyle}]{absDiff[ix]:.4e}[/{aStyle}]",
                style="blue" if relOk or absOk else "red",
            )

            if not (relOk or absOk):
                equal = False

        if printTable:
            console.print(table)

        return equal

    def extractVars(self, y, varGroup, varGroupsIn=None):
        """
        Extract a variable group from a vector

        Args:
            y (numpy.ndarray): the state vector
            varGroup (VarGroup): the variable group to extract
            varGroupsIn ([VarGroup]): the variable groups in ``y``. If ``None``, it
                is assumed that all variable groups with lower indices than
                ``varGroup`` are included in ``y``.

        Returns:
            numpy.ndarray: the subset of ``y`` that corresponds to the ``VarGroup``
            group. The vector elements are reshaped into a matrix if applicable.

        Raises:
            ValueError: if ``y`` doesn't have enough elements to extract the
                requested variable groups
        """
        if varGroupsIn is None:
            varGroupsIn = [v for v in range(varGroup + 1)]
        varGroupsIn = np.array(varGroupsIn, ndmin=1)

        if not varGroup in varGroupsIn:
            raise RuntimeError(
                f"Requested variable group {varGroup} is not part of input set, {varGroupsIn}"
            )

        nPre = sum([self.stateSize(tp) for tp in varGroupsIn if tp < varGroup])
        sz = self.stateSize(varGroup)

        if y.size < nPre + sz:
            raise ValueError(
                f"Need {nPre + sz} vector elements to extract {varGroup} "
                f"but y has size {y.size}"
            )

        nState = self.stateSize(VarGroup.STATE)
        nCol = int(sz / nState)
        if nCol > 1:
            return np.reshape(y[nPre : nPre + sz], (nState, nCol))
        else:
            return np.array(y[nPre : nPre + sz])

    def defaultICs(self, varGroup):
        """
        Get the default initial conditions for a set of equations. This basic
        implementation returns a flattened identity matrix for the :attr:`~VarGroup.STM`
        and zeros for the other equation types. Derived classes can override
        this method to provide other values.

        Args:
            varGroup (VarGroup): describes the group of variables

        Returns:
            numpy.ndarray: initial conditions for the specified equation type
        """
        if varGroup == VarGroup.STM:
            return np.identity(self.stateSize(VarGroup.STATE)).flatten()
        else:
            return np.zeros((self.stateSize(varGroup),))

    def appendICs(self, y0, varsToAppend):
        """
        Append initial conditions for the specified variable groups to the
        provided state vector

        Args:
            y0 (numpy.ndarray): variable vector of arbitrary length
            varsToAppend (VarGroup): the variable group(s) to append initial
                conditions for.

        Returns:
            numpy.ndarray: an initial condition vector, duplicating ``q`` at
            the start of the array with the additional initial conditions
            appended afterward
        """
        y0 = np.asarray(y0)
        varsToAppend = np.array(varsToAppend, ndmin=1)
        nIn = y0.size
        nOut = self.stateSize(varsToAppend)
        y0_out = np.zeros((nIn + nOut,))
        y0_out[:nIn] = y0
        ix = nIn
        for v in sorted(varsToAppend):
            ic = self.defaultICs(v)
            if ic.size > 0:
                y0_out[ix : ix + ic.size] = ic
                ix += ic.size

        return y0_out

    def validForPropagation(self, varGroups):
        """
        Check that the set of variables can be propagated.

        In many cases, some groups of the variables are dependent upon others. E.g.,
        the STM equations of motion generally require the state variables to be
        propagated alongside the STM so ``VarGroup.STM`` would be an invalid set for
        evaluation but ``[VarGroup.STATE, VarGroup.STM]`` would be valid.

        Args:
            varGroups (VarGroup, [VarGroup]): the group(s) variables to be propagated

        Returns:
            bool: True if the set is valid, False otherwise
        """
        # General principle: STATE vars are always required
        return VarGroup.STATE in np.array(varGroups, ndmin=1)

    def varNames(self, varGroup):
        """
        Get names for the variables in each group.

        This implementation provides basic representations of the variables and
        should be overridden by derived classes to give more descriptive names.

        Args:
            varGroup (VarGroup): the variable group

        Returns:
            list of str: a list containing the names of the variables in the order
            they would appear in a variable vector.
        """
        N = self.stateSize(VarGroup.STATE)
        if varGroup == VarGroup.STATE:
            return [f"State {ix:d}" for ix in range(N)]
        elif varGroup == VarGroup.STM:
            return [f"STM({r:d},{c:d})" for r in range(N) for c in range(N)]
        elif varGroup == VarGroup.EPOCH_PARTIALS:
            return [
                f"Epoch Dep {ix:d}"
                for ix in range(self.stateSize(VarGroup.EPOCH_PARTIALS))
            ]
        elif varGroup == VarGroup.PARAM_PARTIALS:
            return [
                f"Param Dep({r:d},{c:d})"
                for r in range(N)
                for c in range(int(self.stateSize(VarGroup.PARAM_PARTIALS) / N))
            ]
        else:
            raise ValueError(f"Unrecognized enum: varGroup = {varGroup}")

    def indexToVarName(self, ix, varGroups):
        # TODO test and document
        allNames = np.asarray(
            [self.varNames(varTp) for varTp in util.toList(varGroups)]
        ).flatten()
        return allNames[ix]


class ModelBlockCopyMixin:
    # A mixin class to prevent another class from copying stored DynamicsModels
    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            if isinstance(v, AbstractDynamicsModel):
                # Models should NOT be copied
                setattr(result, k, v)
            else:
                setattr(result, k, deepcopy(v, memo))
        return result
