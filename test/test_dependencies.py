# -*- coding: utf-8 -*-
"""Very sparse tests for pythontex and depythontex, and tests for hashdependencies."""

from __future__ import unicode_literals

import subprocess
import sys
from contextlib import contextmanager

import pytest

try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path

sys.path.append(str(Path(__file__).parent / "pythontex"))

from depythontex import main as depythontex_main
from pythontex import main as pythontex_main


@pytest.fixture
def in_temp_dir(tmpdir):
    """Run a test in a temporary directory."""
    with tmpdir.as_cwd():
        yield


def run_pdflatex(filename):
    """Run pdflatex on the given file."""
    subprocess.check_call(["pdflatex", "-interaction=nonstopmode", filename])


@contextmanager
def backup_streams():
    """Save stdout and stderr, then restore them on exiting context."""
    stdout = sys.stdout
    stderr = sys.stderr
    try:
        yield
    finally:
        sys.stdout = stdout
        sys.stderr = stderr


def run_pythontex(*argv):
    """Run the pythontex command-line script."""
    with backup_streams():
        # pythontex replaces sys.stdout, which doesn't work twice in a row
        pythontex_main(argv)


def run_depythontex(*argv):
    """Run the depythontex command-line script."""
    with backup_streams():
        # depythontex replaces sys.stdout, which doesn't work twice in a row
        depythontex_main(argv)


def build(filename, pythontex_args=None):
    """Run pdflatex, then pythontex, then pdflatex on the given file."""
    run_pdflatex("test.tex")
    run_pythontex("test.tex", *(pythontex_args or []))
    run_pdflatex("test.tex")


DOCUMENT_TEMPLATE = """
\\documentclass{article}
\\usepackage[%(options)s]{pythontex}
\\begin{document}
%(body)s
\\end{document}
"""


def document(body, options=""):
    """Construct LaTeX document with the given body and pythontex package options."""
    return DOCUMENT_TEMPLATE % dict(body=body, options=options)


def test_build(in_temp_dir):
    """Test building a simple example."""
    Path("test.tex").write_text(document(r"\py{1 + 1}"))
    build("test.tex")
    assert Path("test.pdf").exists()


def convert_tex_to_md(in_filename, out_filename):
    """Use pandoc to convert a tex file into a markdown file."""
    subprocess.check_call(["pandoc", "-o", out_filename, in_filename])


def test_depythontex(in_temp_dir):
    """Test depythontexing a simple example."""
    Path("test.tex").write_text(document(r"\py{1 + 1}", options="depythontex"))
    build("test.tex")
    run_depythontex("-o", "out.tex", "test.tex")
    convert_tex_to_md("out.tex", "out.md")
    assert Path("out.md").read_text().strip() == "2"


@pytest.mark.parametrize("use_hash", (False, True))
def test_rebuild(in_temp_dir, use_hash):
    """Test modifying and rebuilding a simple example."""
    # First, build the document with 1 + 1
    Path("test.tex").write_text(document(r"\py{1 + 1}", options="depythontex"))
    build("test.tex", pythontex_args=["--hashdependencies", str(use_hash).lower()])

    # Edit the document to calculate 2 * 2 instead
    Path("test.tex").write_text(document(r"\py{2 * 2}", options="depythontex"))

    # Build again
    # TODO: this breaks because run_pythontex leaves stdout broken
    build("test.tex", pythontex_args=["--hashdependencies", str(use_hash).lower()])


@pytest.mark.parametrize("use_hash", (False, True))
def test_rebuild_depythontex(in_temp_dir, use_hash):
    """Test modifying, rebuilding, and depythontexing a simple example."""
    # First, build the document with 1 + 1
    Path("test.tex").write_text(document(r"\py{1 + 1}", options="depythontex"))
    build("test.tex", pythontex_args=["--hashdependencies", str(use_hash).lower()])
    run_depythontex("-o", "out.tex", "test.tex")
    convert_tex_to_md("out.tex", "out.md")
    assert Path("out.md").read_text().strip() == "2"

    # Edit the document to calculate 2 * 2 instead
    Path("test.tex").write_text(document(r"\py{2 * 2}", options="depythontex"))

    # Build again
    build("test.tex", pythontex_args=["--hashdependencies", str(use_hash).lower()])
    run_depythontex("--overwrite", "-o", "out.tex", "test.tex")
    convert_tex_to_md("out.tex", "out.md")

    # Make sure the result of the calculation is updated
    assert Path("out.md").read_text().strip() == "4"


@pytest.mark.parametrize("use_hash", (False, True))
def test_dependency(in_temp_dir, use_hash):
    """Test building an example which reads from an external file."""
    Path("data.txt").write_text("hello")
    Path("test.tex").write_text(
        document(r"\py{pytex.open('data.txt').read()}", options="depythontex")
    )
    build("test.tex", pythontex_args=["--hashdependencies", str(use_hash).lower()])
    run_depythontex("-o", "out.tex", "test.tex")
    convert_tex_to_md("out.tex", "out.md")
    assert Path("out.md").read_text().strip() == "hello"


@pytest.mark.parametrize("use_hash", (False, True))
def test_rebuild_dependency(in_temp_dir, use_hash):
    Path("data.txt").write_text("hello")
    Path("test.tex").write_text(
        document(r"\py{pytex.open('data.txt').read()}", options="depythontex")
    )
    build("test.tex", pythontex_args=["--hashdependencies", str(use_hash).lower()])

    # Change content of external file and rebuild
    Path("data.txt").write_text("world")
    build("test.tex", pythontex_args=["--hashdependencies", str(use_hash).lower()])

    # Check the result changed
    run_depythontex("-o", "out.tex", "test.tex")
    convert_tex_to_md("out.tex", "out.md")
    assert Path("out.md").read_text().strip() == "world"
