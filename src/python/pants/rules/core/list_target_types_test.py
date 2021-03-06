# Copyright 2020 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from contextlib import contextmanager
from enum import Enum
from textwrap import dedent
from typing import Optional, cast
from unittest.mock import Mock

from pants.engine.rules import UnionMembership
from pants.engine.target import BoolField, IntField, RegisteredTargetTypes, StringField, Target
from pants.rules.core.list_target_types import list_target_types
from pants.testutil.engine.util import MockConsole, run_rule
from pants.util.ordered_set import OrderedSet


# TODO(#9141): replace this with a proper util to create `GoalSubsystem`s
class MockOptions:
    def __init__(self, **values):
        self.values = Mock(**values)

    @contextmanager
    def line_oriented(self, console: MockConsole):
        yield lambda msg: console.print_stdout(msg)


# Note no docstring.
class FortranVersion(StringField):
    alias = "fortran_version"


class GenericTimeout(IntField):
    """The number of seconds to run before timing out."""

    alias = "timeout"


# Note no docstring, but GenericTimeout has it, so we should end up using that.
class FortranTimeout(GenericTimeout):
    pass


class FortranLibrary(Target):
    """A library of Fortran code."""

    alias = "fortran_library"
    core_fields = (FortranVersion,)


# Note multiline docstring.
class FortranTests(Target):
    """Tests for Fortran code.

    This assumes that you use the FRUIT test framework.
    """

    alias = "fortran_tests"
    core_fields = (FortranVersion, FortranTimeout)


class ArchiveFormat(Enum):
    TGZ = ".tgz"
    TAR = ".tar"


class ArchiveFormatField(StringField):
    alias = "archive_format"
    valid_choices = ArchiveFormat
    default = ArchiveFormat.TGZ.value


class ErrorBehavior(StringField):
    alias = "error_behavior"
    valid_choices = ("ignore", "warn", "error")
    required = True


# Note no docstring.
class FortranBinary(Target):
    alias = "fortran_binary"
    core_fields = (FortranVersion, ArchiveFormatField, ErrorBehavior)


def run_goal(
    *, union_membership: Optional[UnionMembership] = None, details_target: Optional[str] = None
) -> str:
    console = MockConsole(use_colors=False)
    run_rule(
        list_target_types,
        rule_args=[
            RegisteredTargetTypes.create([FortranBinary, FortranLibrary, FortranTests]),
            union_membership or UnionMembership({}),
            MockOptions(details=details_target),
            Mock(),
            console,
        ],
    )
    return cast(str, console.stdout.getvalue())


def test_list_all() -> None:
    stdout = run_goal()
    assert stdout == dedent(
        """\

        Target types
        ------------

        Use `./pants target-types2 --details=$target_type` to get detailed information
        for a particular target type.


        fortran_binary   <no description>

        fortran_library  A library of Fortran code.

        fortran_tests    Tests for Fortran code.
        """
    )


def test_list_single() -> None:
    class CustomField(BoolField):
        """My custom field!

        Use this field to...
        """

        alias = "custom_field"
        required = True

    tests_target_stdout = run_goal(
        union_membership=UnionMembership({FortranTests.PluginField: OrderedSet([CustomField])}),
        details_target=FortranTests.alias,
    )
    assert tests_target_stdout == dedent(
        """\

        fortran_tests
        -------------

        Tests for Fortran code.
        
        This assumes that you use the FRUIT test framework.

        Valid fields:

            custom_field
                type: bool, required
                My custom field! Use this field to...

            fortran_version
                type: str | None, default: None
            
            timeout
                type: int | None, default: None
                The number of seconds to run before timing out.
        """
    )

    binary_target_stdout = run_goal(details_target=FortranBinary.alias)
    assert binary_target_stdout == dedent(
        """\

        fortran_binary
        --------------

        Valid fields:

            archive_format
                type: '.tar' | '.tgz' | None, default: '.tgz'

            error_behavior
                type: 'error' | 'ignore' | 'warn', required

            fortran_version
                type: str | None, default: None
        """
    )
