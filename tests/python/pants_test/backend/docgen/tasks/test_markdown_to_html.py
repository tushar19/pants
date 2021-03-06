# Copyright 2014 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import os
import unittest
import unittest.mock
from textwrap import dedent

import bs4

from pants.backend.docgen.register import build_file_aliases
from pants.backend.docgen.tasks import markdown_to_html_utils
from pants.backend.docgen.tasks.markdown_to_html import MarkdownToHtml
from pants.base.exceptions import TaskError
from pants.testutil.task_test_base import TaskTestBase

ABC = """able
baker
charlie"""


class ChooseLinesTest(unittest.TestCase):
    def test_include_no_params(self):
        self.assertEqual(
            markdown_to_html_utils.choose_include_text(ABC, "", "fake.md"),
            "\n".join(["able", "baker", "charlie"]),
        )

    def test_include_start_at(self):
        self.assertEqual(
            markdown_to_html_utils.choose_include_text(ABC, "start-at=abl", "fake.md"),
            "\n".join(["able", "baker", "charlie"]),
        )

        self.assertEqual(
            markdown_to_html_utils.choose_include_text(ABC, "start-at=bak", "fake.md"),
            "\n".join(["baker", "charlie"]),
        )

        self.assertEqual(
            markdown_to_html_utils.choose_include_text(ABC, "start-at=xxx", "fake.md"), ""
        )

    def test_include_start_after(self):
        self.assertEqual(
            markdown_to_html_utils.choose_include_text(ABC, "start-after=bak", "fake.md"), "charlie"
        )

        self.assertEqual(
            markdown_to_html_utils.choose_include_text(ABC, "start-after=cha", "fake.md"), ""
        )

        self.assertEqual(
            markdown_to_html_utils.choose_include_text(ABC, "start-after=xxx", "fake.md"), ""
        )

    def test_include_end_at(self):
        self.assertEqual(
            markdown_to_html_utils.choose_include_text(ABC, "end-at=abl", "fake.md"), "able"
        )

        self.assertEqual(
            markdown_to_html_utils.choose_include_text(ABC, "end-at=bak", "fake.md"),
            "\n".join(["able", "baker"]),
        )

        self.assertEqual(
            markdown_to_html_utils.choose_include_text(ABC, "end-at=xxx", "fake.md"), ""
        )

    def test_include_end_before(self):
        self.assertEqual(
            markdown_to_html_utils.choose_include_text(ABC, "end-before=abl", "fake.md"), ""
        )

        self.assertEqual(
            markdown_to_html_utils.choose_include_text(ABC, "end-before=xxx", "fake.md"), ""
        )

        self.assertEqual(
            markdown_to_html_utils.choose_include_text(ABC, "end-before=bak", "fake.md"), "able"
        )

    def test_include_start_at_end_at(self):
        self.assertEqual(
            markdown_to_html_utils.choose_include_text(ABC, "start-at=abl&end-at=abl", "fake.md"),
            "able",
        )

        self.assertEqual(
            markdown_to_html_utils.choose_include_text(ABC, "start-at=cha&end-at=cha", "fake.md"),
            "charlie",
        )

        self.assertEqual(
            markdown_to_html_utils.choose_include_text(ABC, "start-at=abl&end-at=bak", "fake.md"),
            "\n".join(["able", "baker"]),
        )

        self.assertEqual(
            markdown_to_html_utils.choose_include_text(ABC, "start-at=bak&end-at=abl", "fake.md"),
            "",
        )


class MarkdownToHtmlTest(TaskTestBase):
    @classmethod
    def task_type(cls):
        return MarkdownToHtml

    @classmethod
    def alias_groups(cls):
        return build_file_aliases()

    def test_rst_render_empty(self):
        self.create_file("empty.rst")
        self.add_to_build_file("", 'page(name = "empty_rst", source = "empty.rst")')
        empty_rst = self.target(":empty_rst")
        task = self.create_task(self.context(target_roots=[empty_rst]))
        task.execute()

    def test_rst_render_failure_fail(self):
        self.create_file(
            "bad.rst",
            contents=dedent(
                """
                A bad link:

                * `RB #2363 https://rbcommons.com/s/twitter/r/2363/>`_
                """
            ),
        )
        self.add_to_build_file("", 'page(name = "bad_rst", source = "bad.rst")')
        bad_rst = self.target(":bad_rst")
        task = self.create_task(self.context(target_roots=[bad_rst]))
        with self.assertRaises(TaskError):
            task.execute()

    def get_rendered_page(self, context, page, rendered_basename):
        pages = context.products.get(MarkdownToHtml.MARKDOWN_HTML_PRODUCT).get(page)
        self.assertIsNotNone(pages)

        pages_by_name = {
            os.path.basename(f): os.path.join(outdir, f)
            for outdir, files in pages.items()
            for f in files
        }
        self.assertIn(rendered_basename, pages_by_name)
        return pages_by_name.get(rendered_basename)

    def test_rst_render_failure_warn(self):
        self.create_file(
            "bad.rst",
            contents=dedent(
                """
                A bad link:

                * `RB #2363 https://rbcommons.com/s/twitter/r/2363/>`_
                """
            ),
        )
        self.add_to_build_file("", 'page(name = "bad_rst", source = "bad.rst")')
        self.set_options(ignore_failure=True)
        bad_rst = self.target(":bad_rst")
        context = self.context(target_roots=[bad_rst])
        context.log.warn = unittest.mock.Mock()
        task = self.create_task(context)
        task.execute()

        # The render error should have been logged.
        self.assertEqual(1, context.log.warn.call_count)
        args, kwargs = context.log.warn.call_args
        self.assertEqual(0, len(kwargs))
        self.assertEqual(1, len(args))
        self.assertIn("bad.rst", args[0])

        # But we still should have gotten (badly) rendered content.
        with open(self.get_rendered_page(context, bad_rst, "bad.html"), "r") as fp:
            html = fp.read()
            self.assertIn("A bad link:", html)

    def test_rst_render_success(self):
        self.create_file(
            "good.rst",
            contents=dedent(
                """
                A good link:

                * `RB #2363 <https://rbcommons.com/s/twitter/r/2363/>`_
                """
            ),
        )
        self.add_to_build_file("", 'page(name = "good_rst", source = "good.rst")')
        good_rst = self.target(":good_rst")
        context = self.context(target_roots=[good_rst])
        task = self.create_task(context)
        task.execute()

        with open(self.get_rendered_page(context, good_rst, "good.html"), "r") as fp:
            html = fp.read()

            soup = bs4.BeautifulSoup(markup=html, features="html.parser")
            self.assertIsNotNone(soup.find(text="A good link:"))

            unordered_list = soup.find(name="ul")
            self.assertIsNotNone(unordered_list)

            list_item = unordered_list.find("li")
            self.assertIsNotNone(list_item)

            anchor = list_item.find(
                "a", attrs={"href": "https://rbcommons.com/s/twitter/r/2363/"}, text="RB #2363"
            )
            self.assertIsNotNone(anchor)
