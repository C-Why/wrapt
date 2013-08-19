"""This module implements decorators for implementing other decorators.

"""

from functools import wraps, partial
from inspect import getargspec

from .wrappers import FunctionWrapper
from .exceptions import (UnexpectedDefaultParameters,
        MissingDefaultParameter, UnexpectedParameters)

# Copy name attributes from a wrapped function onto an wrapper. This is
# only used in mapping the name from the final wrapped function to which
# an adapter is applied onto the adapter itself. All other details come
# from the adapter function via the function wrapper so we don't update
# __dict__ or __wrapped__.

def _update_adapter(wrapper, target):
    for attr in ('__module__', '__name__', '__qualname__'):
        try:
            value = getattr(target, attr)
        except AttributeError:
            pass
        else:
            setattr(wrapper, attr, value)

# Decorators for creating other decorators. These decorators and the
# wrappers which they use are designed to properly preserve any name
# attributes, function signatures etc, in addition to the wrappers
# themselves acting like a transparent proxy for the original wrapped
# function so they the wrapper is effectively indistinguishable from
# the original wrapped function.

WRAPPER_ARGLIST = ('wrapped', 'instance', 'args', 'kwargs')

def decorator(wrapper=None, target=None, **default_params):
    # The decorator works out whether the user decorator will have its
    # own parameters. Parameters for the user decorator must always
    # be specified using keyword arguments and must always have
    # defaults. The user cannot use 'wrapper' or 'target' for their
    # own parameters as we use them ourselves and so they are
    # effectively reserved. The 'wrapper' argument being how the
    # user's wrapper function is passed in. The 'target' argument
    # is used to optionally denote a function which is an adapter,
    # which changes the effective prototype of the wrapped function.
    # The latter is used to ensure that any function argument
    # specification returned by the final result of any decorator is
    # correct and reflects that of the adapter and not the wrapped
    # function.

    if wrapper is not None:
        # The wrapper has been provided, so we must also have any
        # optional default keyword parameters for the user decorator
        # at this point if they were supplied. Before constructing
        # the decorator we validate if the list of supplied default
        # parameters are actually the same as what the users wrapper
        # function expects.

        expected_arglist = WRAPPER_ARGLIST
        complete_arglist = getargspec(wrapper).args

        received_names = set(default_params.keys())
        expected_names = complete_arglist[len(expected_arglist):]

        for name in expected_names:
            try:
                received_names.remove(name)
            except KeyError:
                raise MissingDefaultParameter('Expected value for '
                        'default parameter %r was not supplied for '
                        'decorator %r.' % (name, wrapper.__name__))
        if received_names:
            raise UnexpectedDefaultParameters('Unexpected default '
                    'parameters %r supplied for decorator %r.' % (
                    list(received_names), wrapper.__name__))

        # If we do have default parameters, the final decorator we
        # create needs to be constructed a bit differently as when
        # that decorator is used, it needs to accept parameters.
        # Those parameters need not be supplied, but at least an
        # empty argument list needs to be used on the decorator at
        # that point. When parameters are supplied, they can be as
        # either positional or keyword arguments.

        if len(complete_arglist) > len(expected_arglist):
            # For the case where the decorator is able to accept
            # parameters, return a partial wrapper to collect the
            # parameters.

            @wraps(wrapper)
            def _partial(*decorator_args, **decorator_kwargs):
                # Since the supply of parameters is optional due to
                # having defaults, we need to construct a final set
                # of parameters by overlaying those finally supplied
                # to the decorator at the point of use over the
                # defaults. As we accept positional parameters, we
                # need to translate those back to keyword parameters
                # in the process. This allows us to pass just one
                # dictionary of parameters and we can validate the
                # set of parameters at the point the decorator is
                # used and not only let it fail at the time the
                # wrapped function is called.

                if len(decorator_args) > len(expected_names):
                    raise UnexpectedParameters('Expected at most %r '
                            'positional parameters for decorator %r, '
                            'but received %r.' % (len(expected_names),
                             wrapper.__name__, len(decorator_args)))

                unexpected_params = []
                for name in decorator_kwargs:
                    if name not in default_params:
                        unexpected_params.append(name)

                if unexpected_params:
                    raise UnexpectedParameters('Unexpected parameters '
                            '%r supplied for decorator %r.' % (
                            unexpected_params, wrapper.__name__))

                complete_params = dict(default_params)

                for i, arg in enumerate(decorator_args):
                    if expected_names[i] in decorator_kwargs:
                        raise UnexpectedParameters('Positional parameter '
                                '%r also supplied as keyword parameter '
                                'to decorator %r.' % (expected_names[i],
                                wrapper.__name__))
                    decorator_kwargs[expected_names[i]] = arg

                complete_params.update(decorator_kwargs)

                # Now create and return the final wrapper which
                # combines the parameters with the wrapped function.

                def _wrapper(func):
                    result = FunctionWrapper(wrapped=func, wrapper=wrapper,
                            params=complete_params)
                    if target:
                        _update_adapter(result, target)
                    return result
                return _wrapper

            # Here is where the partial wrapper is returned. This is
            # effectively the users decorator.

            return _partial

        else:
            # No parameters so create and return the final wrapper.
            # This is effectively the users decorator.

            @wraps(wrapper)
            def _wrapper(func):
                result = FunctionWrapper(wrapped=func, wrapper=wrapper)
                if target:
                    _update_adapter(result, target)
                return result
            return _wrapper

    else:
        # The wrapper still has not been provided, so we are just
        # collecting the optional default keyword parameters for the
        # users decorator at this point. Return the decorator again as
        # a partial using the collected default parameters and the
        # adapter function if one is being used.

        return partial(decorator, target=target, **default_params)

def adapter(target):
    @decorator(target=target)
    def wrapper(wrapped, instance, args, kwargs):
        return wrapped(*args, **kwargs)
    return wrapper
