"""
Test Low-Thrust control and dynamics
"""
import numpy as np
import pytest
from conftest import loadBody

from medusa import numerics
from medusa.dynamics import VarGroup
from medusa.dynamics.lowthrust import *

earth = loadBody("Earth")
moon = loadBody("Moon")


class TestControlTerm:
    # Basic test to check type, size, and shape of control term outputs

    @pytest.fixture(
        scope="class",
        params=[
            ["ConstThrustTerm", [2.3], {}],
            ["ConstMassTerm", [123.8], {}],
            ["ConstOrientTerm", [0.1, 2.12], {}],
        ],
        ids=["ConstThrustTerm", "ConstMassTerm", "ConstOrientTerm"],
    )
    def term(self, request):
        cls, args, kwargs = request.param[0], request.param[1], request.param[2]
        obj = eval(cls)(*args, **kwargs)
        obj.register(6, 0)
        return obj

    @pytest.fixture
    def integArgs(self, term):
        nCore = term._coreStateSize
        t = 1.23
        y = np.arange(nCore)
        if term.numStates > 0:
            y = np.concatenate(y, np.arange(nCore, nCore + term.numStates))

        varGroups = (VarGroup.STATE,)
        term._paramIx0 = 1
        return (t, y, varGroups, [99] + term.params)

    def test_constructor(self, term):
        assert isinstance(term, ControlTerm)
        assert term._paramIx0 == 0
        assert term._coreStateSize == 6

    def test_epochIndependent(self, term):
        assert isinstance(term.epochIndependent, bool)

    def test_params(self, term):
        assert isinstance(term.params, list)

    def test_stateICs(self, term):
        assert isinstance(term.stateICs, np.ndarray)
        if term.numStates == 0:
            assert term.stateICs.size == 0
        else:
            assert term.stateICs.shape == (term.numStates,)

    def test_stateDiffEqs(self, term, integArgs):
        eqs = term.stateDiffEqs(*integArgs)
        assert isinstance(eqs, np.ndarray)
        if term.numStates == 0:
            assert eqs.size == 0
        else:
            assert eqs.shape == (term.numStates,)

    def test_evalTerm(self, term, integArgs):
        term.evalTerm(*integArgs)

    def test_partials_term_wrt_coreState(self, term, integArgs):
        partials = term.partials_term_wrt_coreState(*integArgs)
        val = term.evalTerm(*integArgs)
        sz = 1 if isinstance(val, float) else val.size

        assert isinstance(partials, np.ndarray)
        assert partials.shape == (sz, term._coreStateSize)

        # Check partials
        # TODO separate core and ctrl states
        func = lambda x: np.asarray(
            term.evalTerm(integArgs[0], x, *integArgs[2:])
        ).flatten()
        numPartials = numerics.derivative_multivar(func, integArgs[1], 1e-4)
        np.testing.assert_allclose(partials, numPartials, atol=1e-8)

    def test_partials_term_wrt_ctrlState(self, term, integArgs):
        partials = term.partials_term_wrt_ctrlState(*integArgs)
        assert isinstance(partials, np.ndarray)
        if term.numStates == 0:
            assert partials.size == 0
        else:
            val = term.evalTerm(*integArgs)
            sz = 1 if isinstance(val, float) else val.size
            assert partials.shape == (sz, term.numStates)

            # Check partials
            # TODO separate core and ctrl states
            func = lambda x: np.asarray(
                term.evalTerm(integArgs[0], x, *integArgs[2:])
            ).flatten()
            numPartials = numerics.derivative_multivar(func, integArgs[1], 1e-4)
            np.testing.assert_allclose(partials, numPartials, atol=1e-8)

    def test_partials_term_wrt_epoch(self, term, integArgs):
        partials = term.partials_term_wrt_epoch(*integArgs)
        val = term.evalTerm(*integArgs)
        sz = 1 if isinstance(val, float) else val.size

        assert isinstance(partials, np.ndarray)
        assert partials.shape == (sz, 1)
        # TODO zero if epoch idependent

        # Check partials
        func = lambda x: term.evalTerm(x, *integArgs[1:])
        numPartials = numerics.derivative(func, integArgs[0], 1e-4)
        np.testing.assert_allclose(partials, numPartials, atol=1e-8)

    def test_partials_term_wrt_params(self, term, integArgs):
        partials = term.partials_term_wrt_params(*integArgs)
        val = term.evalTerm(*integArgs)
        sz = 1 if isinstance(val, float) else val.size

        assert isinstance(partials, np.ndarray)
        assert partials.shape == (sz, len(integArgs[-1]))

        # Check partials
        func = lambda x: np.asarray(term.evalTerm(*integArgs[:3], x)).flatten()
        numPartials = numerics.derivative_multivar(func, integArgs[3], 1e-4)
        np.testing.assert_allclose(partials, numPartials, atol=1e-8)

    def test_partials_coreStateDEQs_wrt_ctrlState(self, term, integArgs):
        partials = term.partials_coreStateDEQs_wrt_ctrlState(*integArgs)
        assert isinstance(partials, np.ndarray)

        if term.numStates == 0:
            assert partials.size == 0
        else:
            assert partials.shape == (term._coreStateSize, term.numStates)

    def test_partials_ctrlStateDEQs_wrt_coreState(self, term, integArgs):
        partials = term.partials_ctrlStateDEQs_wrt_coreState(*integArgs)
        assert isinstance(partials, np.ndarray)

        if term.numStates == 0:
            assert partials.size == 0
        else:
            assert partials.shape == (term.numStates, term._coreStateSize)

    def test_partials_ctrlStateDEQs_wrt_ctrlState(self, term, integArgs):
        partials = term.partials_ctrlStateDEQs_wrt_ctrlState(*integArgs)
        assert isinstance(partials, np.ndarray)

        if term.numStates == 0:
            assert partials.size == 0
        else:
            assert partials.shape == (term.numStates, term.numStates)

    def test_partials_ctrlStateDEQs_wrt_epoch(self, term, integArgs):
        partials = term.partials_ctrlStateDEQs_wrt_epoch(*integArgs)
        assert isinstance(partials, np.ndarray)

        if term.numStates == 0:
            assert partials.size == 0
        else:
            assert partials.shape == (term.numStates, 1)

    def test_partials_ctrlStateDEQs_wrt_params(self, term, integArgs):
        partials = term.partials_ctrlStateDEQs_wrt_params(*integArgs)
        assert isinstance(partials, np.ndarray)

        if term.numStates == 0 or len(integArgs[-1]) == 0:
            assert partials.size == 0
        else:
            assert partials.shape == (term.numStates, 1)


class TestForceMassOrientLaw_noStates:
    @pytest.fixture()
    def law(self):
        force = ConstThrustTerm(0.011)
        mass = ConstMassTerm(1.0)
        orient = ConstOrientTerm(np.pi / 2, 0.02)
        law = ForceMassOrientLaw(force, mass, orient)
        law.register(6, 0)
        return law

    @pytest.fixture
    def integArgs(self, law):
        nCore = law.terms[0]._coreStateSize
        t = 1.23
        y = np.arange(nCore)
        if law.numStates > 0:
            y = np.concatenate(y, np.arange(nCore, nCore + law.numStates))

        varGroups = (VarGroup.STATE,)
        return (t, y, varGroups, law.params)

    def test_numStates(self, law):
        assert law.numStates == 0

    def test_stateICs(self, law):
        ics = law.stateICs
        assert isinstance(ics, np.ndarray)
        assert ics.size == 0

    def test_stateDiffEqs(self, law, integArgs):
        eqs = law.stateDiffEqs(*integArgs)
        assert isinstance(eqs, np.ndarray)
        assert eqs.size == 0

    def test_stateNames(self, law):
        names = law.stateNames
        assert isinstance(names, list)
        assert names == []  # TODO test with actual named states

    def test_register(self, law):
        law.register(4, 3)
        for term in law.terms:
            assert term._coreStateSize == 4

        assert law.terms[0]._paramIx0 == 3
        assert law.terms[1]._paramIx0 == law.terms[0]._paramIx0 + len(
            law.terms[0].params
        )
        assert law.terms[2]._paramIx0 == law.terms[1]._paramIx0 + len(
            law.terms[1].params
        )

    def test_params(self, law):
        params = law.params
        assert isinstance(params, np.ndarray)
        assert params.shape == (4,)

    def test_accelVec(self, law, integArgs):
        accel = law.accelVec(*integArgs)
        assert isinstance(accel, np.ndarray)
        assert accel.shape == (3, 1)

        mag = np.linalg.norm(accel)
        unit = accel / mag
        assert mag == law.terms[0].evalTerm(*integArgs) / law.terms[1].evalTerm(
            *integArgs
        )
        a, b = law.terms[2].alpha, law.terms[2].beta
        assert unit[0] == np.cos(b) * np.cos(a)
        assert unit[1] == np.cos(b) * np.sin(a)
        assert unit[2] == np.sin(b)

    def test_partials_accel_wrt_coreState(self, law, integArgs):
        partials = law.partials_accel_wrt_coreState(*integArgs)
        assert isinstance(partials, np.ndarray)
        assert partials.shape == (3, law.terms[0]._coreStateSize)

        # Check partials
        # TODO separate core and ctrl states
        func = lambda x: np.asarray(
            law.accelVec(integArgs[0], x, *integArgs[2:])
        ).flatten()
        numPartials = numerics.derivative_multivar(func, integArgs[1], 1e-4)
        np.testing.assert_allclose(partials, numPartials, atol=1e-8)

    def test_partials_accel_wrt_ctrlState(self, law, integArgs):
        partials = law.partials_accel_wrt_ctrlState(*integArgs)
        assert isinstance(partials, np.ndarray)
        assert partials.size == 0

    def test_partials_accel_wrt_epoch(self, law, integArgs):
        partials = law.partials_accel_wrt_epoch(*integArgs)
        assert isinstance(partials, np.ndarray)
        assert partials.shape == (3, 1)

        # Check partials
        func = lambda x: law.accelVec(x, *integArgs[1:])
        numPartials = numerics.derivative(func, integArgs[0], 1e-4)
        np.testing.assert_allclose(partials, numPartials, atol=1e-8)

    def test_partials_accel_wrt_params(self, law, integArgs):
        partials = law.partials_accel_wrt_params(*integArgs)
        assert isinstance(partials, np.ndarray)
        assert partials.shape == (3, len(law.params))

        # Check partials
        func = lambda x: np.asarray(law.accelVec(*integArgs[:3], x)).flatten()
        numPartials = numerics.derivative_multivar(func, integArgs[3], 1e-4)
        np.testing.assert_allclose(partials, numPartials, atol=1e-8)

    def test_partials_ctrlStateDEQs_wrt_coreState(self, law, integArgs):
        partials = law.partials_ctrlStateDEQs_wrt_coreState(*integArgs)
        assert isinstance(partials, np.ndarray)
        assert partials.size == 0

    def test_partials_ctrlStateDEQs_wrt_ctrlState(self, law, integArgs):
        partials = law.partials_ctrlStateDEQs_wrt_ctrlState(*integArgs)
        assert isinstance(partials, np.ndarray)
        assert partials.size == 0

    def test_partials_ctrlStateDEQs_wrt_epoch(self, law, integArgs):
        partials = law.partials_ctrlStateDEQs_wrt_epoch(*integArgs)
        assert isinstance(partials, np.ndarray)
        assert partials.size == 0

    def test_partials_ctrlStateDEQs_wrt_params(self, law, integArgs):
        partials = law.partials_ctrlStateDEQs_wrt_params(*integArgs)
        assert isinstance(partials, np.ndarray)
        assert partials.size == 0
