#!/usr/bin/python3
"""
Test utils borrowed from Brownie.
"""


import warnings

import hypothesis
from hypothesis.errors import HypothesisDeprecationWarning

from .stateful import state_machine  # NOQA: F401
from .strategies import strategy  # NOQA: F401
import boa

# hypothesis warns against combining function-scoped fixtures with @given
# but in brownie this is a documented and useful behaviour. In boa.test we
# will follow the same logic:
warnings.filterwarnings("ignore", category=HypothesisDeprecationWarning)

_hypothesis_given = hypothesis.given


class BoaTestWarning(Warning):
    pass


def given(*given_args, **given_kwargs):
    """Wrapper around hypothesis.given, a decorator for turning a test function
    that accepts arguments into a randomized test.

    This is the main entry point to Hypothesis when using Boa.
    """
    def outer_wrapper(test):
        @boa.env.anchor()
        def isolation_wrapper(*args, **kwargs):
            test(*args, **kwargs)

        # hypothesis.given must wrap the target test to correctly
        # impersonate the call signature for pytest
        hy_given = _hypothesis_given(*given_args, **given_kwargs)
        hy_wrapped = hy_given(test)

        # modify the wrapper name so it shows correctly in test report
        isolation_wrapper.__name__ = test.__name__

        if hasattr(hy_wrapped, "hypothesis"):
            hy_wrapped.hypothesis.inner_test = isolation_wrapper
        return hy_wrapped

    return outer_wrapper