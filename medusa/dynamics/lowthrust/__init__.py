"""
Low-Thrust Dynamics
===================

Control
-------

Low-thrust control can be applied to many different dynamical models, assuming
they are derived with the following assumptions:

- The first six state variables are the Cartesian position and velocity

At the highest level, the :class:`ControlLaw` class computes an acceleration 
vector that is added to the velocity derivatives in the dynamics model. This
control law may define its own state variables and their derivatives for 
inclusion in the model equations of motion. Additionally, the control law
defines all of the relevant partial derivatives so that a state transition 
matrix and other partials can be propagated along with the state for use in
differential corrections.

.. autosummary:: ControlLaw

Separable Control Parameterizations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In many contexts, the low-thrust control is easily separable into independent terms
like thrust force and vector orientation. The :class:`SeparableControlLaw` provides
this type of parameterization via an arbitrary number of :class:`ControlTerm`
objects.

.. autosummary::
   SeparableControlLaw
   ControlTerm

An even more specific parameterization with three terms -- one for thrust force,
one for spacecraft mass, and another for thrust orientation -- is available via
the :class:`ForceMassOrientLaw` with some convenient terms pre-defined.

.. autosummary::
   ForceMassOrientLaw
   ConstThrustTerm
   ConstMassTerm
   ConstOrientTerm

Implementations
---------------

.. toctree::
   :maxdepth: 1

   dynamics.lowthrust.crtbp

Module Reference
----------------

.. autoclass:: ControlTerm
   :members:

.. autoclass:: ConstThrustTerm
   :members:
   :show-inheritance:

.. autoclass:: ConstMassTerm
   :members:
   :show-inheritance:   

.. autoclass:: ConstOrientTerm
   :members:
   :show-inheritance:

.. autoclass:: ControlLaw
   :members:

.. autoclass:: SeparableControlLaw
   :members:
   :show-inheritance:

.. autoclass:: ForceMassOrientLaw
   :members:
   :show-inheritance:
"""

__all__ = [
    # base module
    "ControlTerm",
    "ConstThrustTerm",
    "ConstMassTerm",
    "ConstOrientTerm",
    "ControlLaw",
    "SeparableControlLaw",
    "ForceMassOrientLaw",
    # sub modules
    "crtbp",
]

from abc import ABC, abstractmethod
from typing import Iterable, Union

import numpy as np

from medusa.dynamics import VarGroup

# ------------------------------------------------------------------------------
# Control Terms
# ------------------------------------------------------------------------------


class ControlTerm(ABC):
    """
    Represents a term in the control equations

    .. note:: This is an abstract class and cannot be instantiated.

    Attributes:
        epochIndependent (bool): whether or not this term is independent of the epoch
        numStates (int): the number of extra state variables this term defines
        stateNames ([str]): a list of strings that describe the states
        params (list): the default parameter values
        paramIx0 (int): the index of the first parameter "owned" by this term
            within the full parameter list.
        stateICs (numpy.ndarray): the initial conditions for the state variables
            this term defines.
    """

    def __init__(self) -> None:
        self._coreStateSize = None
        self._paramIx0 = None

    def register(self, nCore: int, ix0: int) -> None:
        """
        Register the control law within the context of the full dynamics model

        Args:
            nCore (int): the number of core states, i.e., the number of state
                variables excluding the control states
            ix0 (int): the index of the first control parameter within the full
                set of parameters.
        """
        self._coreStateSize = nCore
        self._paramIx0 = ix0

    @property
    def epochIndependent(self) -> bool:
        return True

    @property
    def params(self) -> Iterable[float]:
        return []

    @property
    def numStates(self) -> int:
        return 0

    @property
    def stateICs(self) -> Iterable[float]:
        if self.numStates == 0:
            return np.asarray([])
        else:
            return np.zeros((self.numStates,))

    @property
    def stateNames(self) -> Iterable[str]:
        me = self.__class__.__name__
        return [f"{me} {ix}" for ix in range(self.numStates)]

    def stateDiffEqs(
        self,
        t: float,
        w: np.ndarray[float],
        varGroups: tuple[VarGroup, ...],
        params: np.ndarray[float],
    ) -> np.ndarray[float]:
        """
        Defines the differential equations that govern the state variables this
        term defines, i.e., derivatives of the state variables with respect to
        integration time.

        The input arguments are consistent with those passed to the
        :func:`medusa.dynamics.AbstractDynamicsModel.diffEqs` function.

        .. note:: This method is implemented to return zeros for all state variables
           by default. Override it to define custom behavior.

        Returns:
            the time derivatives of the state variables. If this
            term doesn't define any state variables, an empty array is returned.
        """
        if self.numStates == 0:
            return np.asarray([])
        else:
            return np.zeros((self.numStates,))

    @abstractmethod
    def evalTerm(
        self,
        t: float,
        w: np.ndarray[float],
        varGroups: tuple[VarGroup, ...],
        params: np.ndarray[float],
    ) -> Union[float, np.ndarray[float]]:
        """
        Evaluate the term.

        The input arguments are consistent with those passed to the
        :func:`medusa.dynamics.AbstractDynamicsModel.diffEqs` function.

        Returns:
            the evaluated term
        """
        pass

    @abstractmethod
    def partials_term_wrt_coreState(
        self,
        t: float,
        w: np.ndarray[float],
        varGroups: tuple[VarGroup, ...],
        params: np.ndarray[float],
    ) -> np.ndarray[float]:
        """
        Compute the partial derivatives of :func:`evalTerm` with respect to the
        "core state", i.e., the state variables that exist independently of the
        control parametrization.

        The input arguments are consistent with those passed to the
        :func:`medusa.dynamics.AbstractDynamicsModel.diffEqs` function.

        Returns:
            the partial derivatives where the rows represent the
            elements in :func:`evalTerm` and the columns represent the core states.
        """
        pass

    @abstractmethod
    def partials_term_wrt_ctrlState(
        self,
        t: float,
        w: np.ndarray[float],
        varGroups: tuple[VarGroup, ...],
        params: np.ndarray[float],
    ) -> np.ndarray[float]:
        """
        Compute the partial derivatives of :func:`evalTerm` with respect to the
        control state variables that are defined by *this term*.

        The input arguments are consistent with those passed to the
        :func:`medusa.dynamics.AbstractDynamicsModel.diffEqs` function.

        Returns:
            the partial derivatives
        """
        pass

    @abstractmethod
    def partials_term_wrt_epoch(
        self,
        t: float,
        w: np.ndarray[float],
        varGroups: tuple[VarGroup, ...],
        params: np.ndarray[float],
    ) -> np.ndarray[float]:
        """
        Compute the partial derivatives of :func:`evalTerm` with respect to the epoch.

        The input arguments are consistent with those passed to the
        :func:`medusa.dynamics.AbstractDynamicsModel.diffEqs` function.

        Returns:
            the partial derivatives where the rows represent the
            elements in :func:`evalTerm` and the column represents the epoch.
        """
        pass

    @abstractmethod
    def partials_term_wrt_params(
        self,
        t: float,
        w: np.ndarray[float],
        varGroups: tuple[VarGroup, ...],
        params: np.ndarray[float],
    ) -> np.ndarray[float]:
        """
        Compute the partial derivatives of :func:`evalTerm` with respect to the
        parameters *this term* defines.

        The input arguments are consistent with those passed to the
        :func:`medusa.dynamics.AbstractDynamicsModel.diffEqs` function.

        Returns:
            the partial derivatives where the rows represent the
            elements in :func:`evalTerm` and the columns represent the parameters.
        """
        pass

    def partials_coreStateDEQs_wrt_ctrlState(
        self,
        t: float,
        w: np.ndarray[float],
        varGroups: tuple[VarGroup, ...],
        params: np.ndarray[float],
    ) -> np.ndarray[float]:
        """
        Compute the partial derivatives of the core state differential equations
        (defined in :func:`~medusa.dynamics.AbstractDynamicsModel.diffEqs`) with
        respect to the control state variables that are defined by this term.

        The input arguments are consistent with those passed to the
        :func:`medusa.dynamics.AbstractDynamicsModel.diffEqs` function.

        Returns:
            the partial derivatives where the rows represent the
            core states and the columns represent the control states defined by
            this term. If this term doesn't define any control states, an
            empty array is returned.
        """
        if self.numStates == 0:
            return np.asarray([])
        else:
            return np.zeros((self._coreStateSize, self.numStates))

    def partials_ctrlStateDEQs_wrt_coreState(
        self,
        t: float,
        w: np.ndarray[float],
        varGroups: tuple[VarGroup, ...],
        params: np.ndarray[float],
    ) -> np.ndarray[float]:
        """
        Compute the partial derivatives of :func:`stateDiffEqs` with respect to
        the "core state," i.e., the state variables that exist independent of the
        control parameterization.

        The input arguments are consistent with those passed to the
        :func:`medusa.dynamics.AbstractDynamicsModel.diffEqs` function.

        Returns:
            the partial derivatives where the rows represent the
            elements in :func:`stateDiffEqs` and the columns represent the core
            states. If this term doesn't define any control states, an empty
            array is returned.
        """
        if self.numStates == 0:
            return np.asarray([])
        else:
            return np.zeros((self.numStates, self._coreStateSize))

    def partials_ctrlStateDEQs_wrt_ctrlState(
        self,
        t: float,
        w: np.ndarray[float],
        varGroups: tuple[VarGroup, ...],
        params: np.ndarray[float],
    ) -> np.ndarray[float]:
        """
        Compute the partial derivatives of :func:`stateDiffEqs` with respect to
        the control state variables defined by this term.

        The input arguments are consistent with those passed to the
        :func:`medusa.dynamics.AbstractDynamicsModel.diffEqs` function.

        Returns:
            the partial derivatives where the rows represent the
            elements in :func:`stateDiffEqs` and the columns represent the core
            states. If this term doesn't define any control states, an empty
            array is returned.
        """
        if self.numStates == 0:
            return np.asarray([])
        else:
            return np.zeros((self.numStates, self.numStates))

    def partials_ctrlStateDEQs_wrt_epoch(
        self,
        t: float,
        w: np.ndarray[float],
        varGroups: tuple[VarGroup, ...],
        params: np.ndarray[float],
    ) -> np.ndarray:
        """
        Compute the partial derivatives of :func:`stateDiffEqs` with respect to
        the epoch.

        The input arguments are consistent with those passed to the
        :func:`medusa.dynamics.AbstractDynamicsModel.diffEqs` function.

        Returns:
            the partial derivatives where the rows represent the
            elements in :func:`stateDiffEqs` and the column represents epoch.
            If this term doesn't define any control states, an empty array is
            returned.
        """
        if self.numStates == 0:
            return np.asarray([])
        else:
            return np.zeros((self.numStates,))

    def partials_ctrlStateDEQs_wrt_params(
        self,
        t: float,
        w: np.ndarray[float],
        varGroups: tuple[VarGroup, ...],
        params: np.ndarray[float],
    ) -> np.ndarray[float]:
        """
        Compute the partial derivatives of :func:`stateDiffEqs` with respect to
        the parameters defined by this term.

        The input arguments are consistent with those passed to the
        :func:`medusa.dynamics.AbstractDynamicsModel.diffEqs` function.

        Returns:
            the partial derivatives where the rows represent the
            elements in :func:`stateDiffEqs` and the columns represent the
            parameters. If this term doesn't define any control states, an empty
            array is returned.
        """
        if self.numStates == 0 or len(params) == 0:
            return np.asarray([])
        else:
            return np.zeros((self.numStates, len(params)))


class ConstThrustTerm(ControlTerm):
    """
    Defines a constant thrust. The thrust is stored as a parameter.

    Args:
        thrust: the thrust force in units consistent with the model
            (i.e., if the model nondimensionalizes values, this value should
            also be nondimensionalized).
    """

    def __init__(self, thrust: float) -> None:
        super().__init__()
        self.thrust = thrust

    @property
    def params(self):
        return [self.thrust]

    def evalTerm(self, t, w, varGroups, params):
        return params[self._paramIx0]

    def partials_term_wrt_coreState(self, t, w, varGroups, params):
        return np.zeros((1, self._coreStateSize))

    def partials_term_wrt_ctrlState(self, t, w, varGroups, params):
        return np.asarray([])  # No control states

    def partials_term_wrt_epoch(self, t, w, varGroups, params):
        return np.array([0], ndmin=2)

    def partials_term_wrt_params(self, t, w, varGroups, params):
        partials = np.zeros((1, len(params)))
        partials[0, self._paramIx0] = 1
        return partials


class ConstMassTerm(ControlTerm):
    """
    Defines a constant mass. The mass is stored as a parameter.

    Args:
        mass: the mass in units consistent with the model
            (i.e., if the model nondimensionalizes values, this value should
            also be nondimensionalized).
    """

    def __init__(self, mass: float) -> None:
        super().__init__()
        self.mass = mass

    @property
    def params(self):
        return [self.mass]

    def evalTerm(self, t, w, varGroups, params):
        return params[self._paramIx0]

    def partials_term_wrt_coreState(self, t, w, varGroups, params):
        return np.zeros((1, self._coreStateSize))

    def partials_term_wrt_ctrlState(self, t, w, varGroups, params):
        return np.asarray([])  # No control states

    def partials_term_wrt_epoch(self, t, w, varGroups, params):
        return np.array([0], ndmin=2)

    def partials_term_wrt_params(self, t, w, varGroups, params):
        partials = np.zeros((1, len(params)))
        partials[0, self._paramIx0] = 1
        return partials


class ConstOrientTerm(ControlTerm):
    """
    Defines a constant thrust orientation in the working frame. Orientation
    is parameterized via spherical angles alpha and beta, which are stored as
    parameters

    Args:
        alpha: the angle between the projection of the thrust vector
            into the xy-plane and the x-axis, measured about the z-axis. Units
            are radians.
        beta: the angle between the thrust vector and the xy-plane. A
            positive value corresponds to a positive z-component. Units are
            radians.
    """

    def __init__(self, alpha: float, beta: float) -> None:
        super().__init__()
        self.alpha = alpha
        self.beta = beta

    @property
    def params(self):
        return [self.alpha, self.beta]

    def _getAngles(self, params):
        return params[self._paramIx0], params[self._paramIx0 + 1]

    def evalTerm(self, t, w, varGroups, params):
        alpha, beta = self._getAngles(params)
        return np.asarray(
            [
                [np.cos(beta) * np.cos(alpha)],
                [np.cos(beta) * np.sin(alpha)],
                [np.sin(beta)],
            ]
        )

    def partials_term_wrt_coreState(self, t, w, varGroups, params):
        return np.zeros((3, self._coreStateSize))

    def partials_term_wrt_ctrlState(self, t, w, varGroups, params):
        return np.asarray([])  # no control states

    def partials_term_wrt_epoch(self, t, w, varGroups, params):
        return np.zeros((3, 1))

    def partials_term_wrt_params(self, t, w, varGroups, params):
        partials = np.zeros((3, len(params)))
        alpha, beta = self._getAngles(params)
        partials[:, self._paramIx0] = [
            -np.cos(beta) * np.sin(alpha),
            np.cos(beta) * np.cos(alpha),
            0,
        ]
        partials[:, self._paramIx0 + 1] = [
            -np.sin(beta) * np.cos(alpha),
            -np.sin(beta) * np.sin(alpha),
            np.cos(beta),
        ]
        return partials


# ------------------------------------------------------------------------------
# Control Laws
# ------------------------------------------------------------------------------


class ControlLaw(ABC):
    """
    Interface definition for a low-thrust control law

    Attributes:
        epochIndepdnent (bool): whether or not the control parameterization is
            epoch-independent.
        numStates (int): the number of state variables defined by the control law
        stateNames (list of str): the names of the state variables defined by
            the control law
        params (list of float): the default parameter values for the control law
    """

    def __init__(self) -> None:
        self._coreStateSize = None
        self._paramIx0 = None

    def register(self, nCore, ix0):
        """
        Register the control law within the context of the full dynamics model

        Args:
            nCore (int): the number of core states, i.e., the number of state
                variables excluding the control states
            ix0 (int): the index of the first control parameter within the full
                set of parameters.
        """
        self._coreStateSize = nCore
        self._paramIx0 = ix0

    @abstractmethod
    def accelVec(self, t, w, varGroups, params):
        """
        Compute the acceleration vector delivered by this control law.

        The input arguments are consistent with those passed to the
        :func:`medusa.dynamics.AbstractDynamicsModel.diffEqs` function.

        Returns:
            numpy.ndarray: a 3x1 array that gives the Cartesian acceleration
            vector.
        """
        pass

    @property
    @abstractmethod
    def epochIndependent(self):
        pass

    @property
    @abstractmethod
    def numStates(self):
        pass

    @property
    @abstractmethod
    def stateNames(self):
        pass

    @property
    @abstractmethod
    def params(self):
        pass

    @abstractmethod
    def stateDiffEqs(self, t, w, varGroups, params):
        """
        Defines the differential equations that govern the state variables this
        control law defines, i.e., derivatives of the state variables with respect
        to integration time.

        The input arguments are consistent with those passed to the
        :func:`medusa.dynamics.AbstractDynamicsModel.diffEqs` function.

        Returns:
            numpy.ndarray: the time derivatives of the state variables. If this
            term doesn't define any state variables, an empty array is returned.
        """
        pass

    @abstractmethod
    def partials_accel_wrt_coreState(self, t, w, varGroups, params):
        """
        The partial derivatives of :func:`accelVec` with respect to the "core state,"
        i.e., the state variables that exist independent of the control
        parameterization.

        The input arguments are consistent with those passed to the
        :func:`medusa.dynamics.AbstractDynamicsModel.diffEqs` function.

        Returns:
            numpy.ndarray: the partial derivatives; the rows represent the elements
            of the acceleration vector and the columns represent the core state
            variables.
        """
        pass

    @abstractmethod
    def partials_accel_wrt_ctrlState(self, t, w, varGroups, params):
        """
        The partial derivatives of :func:`accelVec` with respect to the control
        states defined by the control law.

        The input arguments are consistent with those passed to the
        :func:`medusa.dynamics.AbstractDynamicsModel.diffEqs` function.

        Returns:
            numpy.ndarray: the partial derivatives; the rows represent the elements
            of the acceleration vector and the columns represent the control state
            variables.
        """
        pass

    @abstractmethod
    def partials_accel_wrt_epoch(self, t, w, varGroups, params):
        """
        The partial derivatives of :func:`accelVec` with respect to the epoch.

        The input arguments are consistent with those passed to the
        :func:`medusa.dynamics.AbstractDynamicsModel.diffEqs` function.

        Returns:
            numpy.ndarray: the partial derivatives; the rows represent the elements
            of the acceleration vector and the column represents the epoch.
        """
        pass

    @abstractmethod
    def partials_accel_wrt_params(self, t, w, varGroups, params):
        """
        The partial derivatives of :func:`accelVec` with respect to the parameters
        defined by the control law.

        The input arguments are consistent with those passed to the
        :func:`medusa.dynamics.AbstractDynamicsModel.diffEqs` function.

        Returns:
            numpy.ndarray: the partial derivatives; the rows represent the elements
            of the acceleration vector and the columns represent the parameters.
        """
        pass

    @abstractmethod
    def partials_ctrlStateDEQs_wrt_coreState(self, t, w, varGroups, params):
        """
        The partial derivatives of :func:`stateDiffEqs` with respect to the "core
        states," i.e., the state variables that exist independently of the
        control parameterization.

        The input arguments are consistent with those passed to the
        :func:`medusa.dynamics.AbstractDynamicsModel.diffEqs` function.

        Returns:
            numpy.ndarray: the partial derivatives; the rows represent the
            differential equations and the columns represent the core state
            variables.
        """
        pass

    @abstractmethod
    def partials_ctrlStateDEQs_wrt_ctrlState(self, t, w, varGroups, params):
        """
        The partial derivatives of :func:`stateDiffEqs` with respect to the state
        variables defined by the control law.

        The input arguments are consistent with those passed to the
        :func:`medusa.dynamics.AbstractDynamicsModel.diffEqs` function.

        Returns:
            numpy.ndarray: the partial derivatives; the rows represent the
            differential equations and the columns represent the control state
            variables.
        """
        pass

    @abstractmethod
    def partials_ctrlStateDEQs_wrt_epoch(self, t, w, varGroups, params):
        """
        The partial derivatives of :func:`stateDiffEqs` with respect to the epoch.

        The input arguments are consistent with those passed to the
        :func:`medusa.dynamics.AbstractDynamicsModel.diffEqs` function.

        Returns:
            numpy.ndarray: the partial derivatives; the rows represent the
            differential equations and the column represents the epoch.
        """
        pass

    @abstractmethod
    def partials_ctrlStateDEQs_wrt_params(self, t, w, varGroups, params):
        """
        The partial derivatives of :func:`stateDiffEqs` with respect to the
        parameters defined by the control law.

        The input arguments are consistent with those passed to the
        :func:`medusa.dynamics.AbstractDynamicsModel.diffEqs` function.

        Returns:
            numpy.ndarray: the partial derivatives; the rows represent the
            differential equations and the columns represent the parameters.
        """
        pass


class SeparableControlLaw(ControlLaw):
    """
    A control law implementation with "separable" terms. In this context,
    separable means that each term defines state variables and parameters
    independently of the other terms. As a result, the control state
    differential equations and their partial derivatives can be concatenated
    without additional calculus to relate the terms.

    .. note:: This implementation is abstract; derived objects must define the
       acceleration vector and its associated partial derivatives.

    Args:
        terms: the term(s) to include in the control parameterization.
    """

    def __init__(self, *terms: Iterable[ControlTerm]) -> None:
        self.terms = tuple(terms)

    def _concat(self, arrays):
        """
        Concatenate numpy arrays. This convenience method skips concatenation of
        empty arrays, avoiding errors.
        """
        out = arrays[0]
        for array in arrays[1:]:
            if np.asarray(array).size > 0:
                out = np.concatenate((out, array))

        return out

    @property
    def epochIndependent(self):
        return all(term.epochIndependent for term in self.terms)

    @property
    def numStates(self):
        return sum(term.numStates for term in self.terms)

    @property
    def stateNames(self):
        return self._concat([term.stateNames for term in self.terms])

    @property
    def params(self):
        return self._concat([term.params for term in self.terms])

    def stateICs(self):
        return self._concat([term.stateICs for term in self.terms])

    def stateDiffEqs(self, t, w, varGroups, params):
        return self._concat(
            [term.stateDiffEqs(t, w, varGroups, params) for term in self.terms]
        )

    def register(self, nCore, ix0):
        """
        Register the control law within the context of the dynamics model

        Args:
            nCore (int): the number of core states, i.e., the number of state
                variables excluding the control states
            ix0 (int): the index of the first control parameter within the full
                set of parameters.
        """
        super().register(nCore, ix0)

        for term in self.terms:
            term.register(nCore, ix0)
            ix0 += len(term.params)

    def partials_ctrlStateDEQs_wrt_coreState(self, t, w, varGroups, params):
        # Because the control terms are independent, we can just concatenate
        #   the partial derivatives of the control state diff eqs.
        return self._concat(
            [
                term.partials_ctrlStateDEQs_wrt_coreState(t, w, varGroups, params)
                for term in self.terms
            ]
        )

    def partials_ctrlStateDEQs_wrt_ctrlState(self, t, w, varGroups, params):
        return self._concat(
            [
                term.partials_ctrlStateDEQs_wrt_ctrlState(t, w, varGroups, params)
                for term in self.terms
            ]
        )

    def partials_ctrlStateDEQs_wrt_epoch(self, t, w, varGroups, params):
        return self._concat(
            [
                term.partials_ctrlStateDEQs_wrt_epoch(t, w, varGroups, params)
                for term in self.terms
            ]
        )

    def partials_ctrlStateDEQs_wrt_params(self, t, w, varGroups, params):
        return self._concat(
            [
                term.partials_ctrlStateDEQs_wrt_params(t, w, varGroups, params)
                for term in self.terms
            ]
        )


class ForceMassOrientLaw(SeparableControlLaw):
    """
    A separable control law that accepts three terms: force, mass, and orientation.

    Args:
        force: defines the scalar thrust force
        mass: defines the scalar mass
        orient: defines the unit vector that orients the thrust

    The acceleration is computed as: :math:`\\vec{a} = \\frac{f}{m} \\hat{u}`
    where :math:`f` is the thrust force, :math:`m` is the mass, and
    :math:`\\hat{u}` is the orientation.
    """

    def __init__(
        self, force: ControlTerm, mass: ControlTerm, orient: ControlTerm
    ) -> None:
        super().__init__(force, mass, orient)

    def accelVec(self, t, w, varGroups, params):
        # Returns Cartesian acceleration vector
        force = self.terms[0].evalTerm(t, w, varGroups, params)
        mass = self.terms[1].evalTerm(t, w, varGroups, params)
        vec = self.terms[2].evalTerm(t, w, varGroups, params)

        return (force / mass) * vec

    def _accelPartials(self, t, w, varGroups, params, partialFcn):
        # Use chain rule to combine partials of the acceleration w.r.t. some other
        #   parameter
        f = self.terms[0].evalTerm(t, w, varGroups, params)
        m = self.terms[1].evalTerm(t, w, varGroups, params)
        vec = self.terms[2].evalTerm(t, w, varGroups, params)

        dfdX = getattr(self.terms[0], partialFcn)(t, w, varGroups, params)
        dmdX = getattr(self.terms[1], partialFcn)(t, w, varGroups, params)
        dodX = getattr(self.terms[2], partialFcn)(t, w, varGroups, params)

        term1 = (vec @ dfdX / m) if dfdX.size > 0 else 0
        term2 = (-f * vec / (m * m)) @ dmdX if dmdX.size > 0 else 0
        term3 = (f / m) * dodX if dodX.size > 0 else 0

        partials = term1 + term2 + term3
        return np.asarray([]) if isinstance(partials, int) else partials

    def partials_accel_wrt_coreState(self, t, w, varGroups, params):
        return self._accelPartials(
            t, w, varGroups, params, "partials_term_wrt_coreState"
        )

    def partials_accel_wrt_ctrlState(self, t, w, varGroups, params):
        return self._accelPartials(
            t, w, varGroups, params, "partials_term_wrt_ctrlState"
        )

    def partials_accel_wrt_epoch(self, t, w, varGroups, params):
        return self._accelPartials(t, w, varGroups, params, "partials_term_wrt_epoch")

    def partials_accel_wrt_params(self, t, w, varGroups, params):
        return self._accelPartials(t, w, varGroups, params, "partials_term_wrt_params")
