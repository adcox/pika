"""
Test Constraint objects
"""
import numpy as np
import pytest
from conftest import loadBody

import pika.corrections.constraints as pcons
from pika.corrections import ControlPoint, CorrectionsProblem, Segment, Variable


class TestContinuityConstraint:
    @pytest.fixture(scope="class")
    def model(self):
        from pika.crtbp import DynamicsModel

        earth, moon = loadBody("Earth"), loadBody("Moon")
        return DynamicsModel(earth, moon)

    @pytest.fixture
    def origin(self, model, originMask):
        # IC for EM L3 Vertical
        state = Variable([0.8213, 0.0, 0.5690, 0.0, -1.8214, 0.0], originMask)
        return ControlPoint(model, 0.1, state)

    @pytest.fixture
    def terminus(self, model, terminusMask):
        state = Variable([0.0] * 6, terminusMask)
        return ControlPoint(model, 1.1, state)

    @pytest.fixture
    def segment(self, origin, terminus):
        return Segment(origin, 1.0, terminus=terminus)

    @pytest.fixture
    def problem(self, segment):
        prob = CorrectionsProblem()
        prob.addVariables(segment.origin.state)
        prob.addVariables(segment.terminus.state)
        prob.addVariables(segment.tof)
        prob.addVariables(segment.propParams)

        return prob

    @pytest.mark.parametrize(
        "originMask, terminusMask, indices",
        [
            [None, None, None],
            [None, None, [0, 1, 2]],
            [None, [0, 0, 0, 1, 1, 1], [0, 1, 2]],
        ],
    )
    def test_constructor(self, segment, indices):
        con = pcons.ContinuityConstraint(segment, indices=indices)

    @pytest.mark.parametrize(
        "originMask, terminusMask, indices",
        [
            [None, [0, 1, 0, 0, 0, 0], None],
            [None, [0, 1, 0, 0, 0, 0], [0, 1, 2]],
        ],
    )
    def test_constructor_incompatibleMasks(self, segment, indices):
        with pytest.raises(RuntimeError):
            pcons.ContinuityConstraint(segment, indices=indices)

    @pytest.mark.parametrize(
        "originMask, terminusMask, indices",
        [
            [None, None, None],
            [None, None, [0, 1, 2]],
            [None, [0, 0, 0, 1, 1, 1], [0, 1, 2]],
            [[0, 0, 0, 1, 1, 1], None, None],
            [[0, 1, 0, 1, 1, 1], None, None],
            [[0, 0, 0, 1, 1, 1], None, [0, 1, 2]],
            [[0, 0, 0, 1, 1, 1], [0, 0, 0, 1, 1, 1], [0, 1, 2]],
        ],
    )
    def test_evaluate(self, segment, indices, problem):
        con = pcons.ContinuityConstraint(segment, indices=indices)
        err = con.evaluate(problem.freeVarIndexMap())
        assert isinstance(err, np.ndarray)
        assert err.size == con.size

    @pytest.mark.parametrize(
        "originMask, terminusMask, indices",
        [
            [None, None, None],
            [None, None, [0, 1, 2]],
            [None, [0, 0, 0, 1, 1, 1], [0, 1, 2]],
            [[0, 0, 0, 1, 1, 1], None, None],
            [[0, 1, 0, 1, 1, 1], None, None],
            [[0, 0, 0, 1, 1, 1], None, [0, 1, 2]],
            [[0, 0, 0, 1, 1, 1], [0, 0, 0, 1, 1, 1], [0, 1, 2]],
        ],
    )
    def test_partials(self, segment, indices, problem):
        con = pcons.ContinuityConstraint(segment, indices=indices)
        partials = con.partials(problem.freeVarIndexMap())

        assert isinstance(partials, dict)

        assert segment.origin.state in partials
        dF_dq0 = partials[segment.origin.state]
        assert isinstance(dF_dq0, np.ndarray)
        assert dF_dq0.shape == (con.size, segment.origin.state.numFree)

        assert segment.terminus.state in partials
        dF_dqf = partials[segment.terminus.state]
        assert isinstance(dF_dqf, np.ndarray)
        assert dF_dqf.shape == (con.size, segment.terminus.state.numFree)

        assert segment.tof in partials
        dF_dtof = partials[segment.tof]
        assert isinstance(dF_dtof, np.ndarray)
        assert dF_dtof.shape == (con.size,)

        assert not segment.propParams in partials
        assert not segment.origin.epoch in partials
        assert not segment.terminus.epoch in partials

    @pytest.mark.parametrize(
        "originMask, terminusMask, indices",
        [
            [None, None, None],
            [None, None, [0, 1, 2]],
            [None, [0, 0, 0, 1, 1, 1], [0, 1, 2]],
            [[0, 0, 0, 1, 1, 1], None, None],
            [[0, 1, 0, 1, 1, 1], None, None],
            [[0, 0, 0, 1, 1, 1], None, [0, 1, 2]],
            [[0, 0, 0, 1, 1, 1], [0, 0, 0, 1, 1, 1], [0, 1, 2]],
        ],
    )
    def test_excludeTerminus(self, segment, indices):
        # Don't include the terminus in the free variable vector
        prob = CorrectionsProblem()
        prob.addVariables(segment.origin.state)
        prob.addVariables(segment.tof)
        con = pcons.ContinuityConstraint(segment, indices=indices)
        err = con.evaluate(prob.freeVarIndexMap())
        assert isinstance(err, np.ndarray)
        assert err.size == con.size

        partials = con.partials(prob.freeVarIndexMap())
        assert not segment.terminus.state in partials
        assert segment.origin.state in partials
        assert segment.tof in partials
        assert not segment.propParams in partials
        assert not segment.origin.epoch in partials
        assert not segment.terminus.epoch in partials


class TestVariableValueConstraint:
    @pytest.mark.parametrize(
        "var",
        [
            Variable([1.0, 2.0]),
            Variable([1.0, 2.0, 3.0], [False, False, True]),
        ],
    )
    @pytest.mark.parametrize("values", [[0.0, 0.0], [None, 0.0], [None, None]])
    def test_constructor(self, var, values):
        con = pcons.VariableValueConstraint(var, values)
        assert con.variable == var

        assert isinstance(con.values, np.ma.MaskedArray)
        assert np.array_equal(con.values, values)
        assert np.array_equal(con.values.mask, [v is None for v in values])

    @pytest.mark.parametrize(
        "var",
        [
            Variable([1.0]),  # incorrect number of elements
            Variable([1.0, 2.0], [True, False]),  # incorrect number of free vars
            np.array([1.0, 2.0]),  # incorrect type
        ],
    )
    def test_constructor_errors(self, var):
        with pytest.raises(ValueError):
            pcons.VariableValueConstraint(var, [0.0, 0.0])

    @pytest.mark.parametrize(
        "var",
        [
            Variable([1.0, 2.0]),
            Variable([1.0, 2.0, 3.0], [False, False, True]),
        ],
    )
    @pytest.mark.parametrize("values", [[0.0, 0.0], [None, 0.0], [None, None]])
    def test_size(self, var, values):
        con = pcons.VariableValueConstraint(var, values)
        assert con.size == sum([v is not None for v in values])

    @pytest.mark.parametrize("values", [[0.0, 0.0], [None, 0.0], [None, None]])
    def test_evaluate(self, values):
        var = Variable([1.0, 2.0])
        con = pcons.VariableValueConstraint(var, values)
        indexMap = {var: 3}
        conEval = con.evaluate(indexMap)

        assert isinstance(conEval, np.ndarray)
        assert conEval.size == con.size

        # Constraint eval should use free variable values from the vector, NOT
        #   from the object used to construct the constraint
        count = 0
        for ix in range(len(con.values)):
            if not con.values.mask[ix]:
                assert conEval[count] == var.freeVals[ix] - con.values[ix]
                count += 1

    @pytest.mark.parametrize("values", [[0.0, 0.0], [None, 0.0], [None, None]])
    def test_partials(self, values):
        var = Variable([1.0, 2.0])
        con = pcons.VariableValueConstraint(var, values)
        indexMap = {var: 3}
        partials = con.partials(indexMap)

        assert isinstance(partials, dict)
        assert var in partials
        assert len(partials) == 1

        assert partials[var].shape == (con.size, var.numFree)

        count = 0
        for ix in range(len(con.values)):
            if not con.values.mask[ix]:
                assert partials[var][count, ix] == 1
                count += 1

    def test_varsAreRefs(self):
        var = Variable([1.0, 2.0])
        con = pcons.VariableValueConstraint(var, [0.0, 1.0])
        indexMap = {var: 0}

        conEval = con.evaluate(indexMap)
        assert np.array_equal(conEval, [1.0, 1.0])

        # Update variable
        var.values[:] = [0.0, 1.0]
        conEval2 = con.evaluate(indexMap)
        assert np.array_equal(conEval2, [0.0, 0.0])
