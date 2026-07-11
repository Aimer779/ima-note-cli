from __future__ import annotations

import unittest

from tests._bootstrap import ROOT  # noqa: F401
from ima_note_cli.notes_content import prepare_note_markdown


class NotesContentTests(unittest.TestCase):
    def test_unicode_and_network_images_are_preserved(self):
        content = "中文\n![a](http://example.com/a.png)\n![b](https://example.com/b.png)"
        prepared = prepare_note_markdown(content)
        self.assertEqual(prepared.content, content)
        self.assertEqual(prepared.removed_local_images, ())

    def test_local_markdown_image_variants_are_removed_in_order(self):
        paths = [
            "file:///tmp/a.png", "C:\\images\\b.png", "\\\\server\\share\\c.png",
            "/tmp/d.png", "./e.png", "../f.png", "~/g.png", "image.png", "data:image/png;base64,AA",
        ]
        content = "正文\n" + "\n".join(f"![x]({path})" for path in paths)
        prepared = prepare_note_markdown(content)
        self.assertEqual(prepared.removed_local_images, tuple(paths))
        self.assertNotIn("![", prepared.content)
        self.assertTrue(prepared.warnings)

    def test_html_images_are_filtered_but_network_src_is_preserved(self):
        content = '<img src="./local.png" alt="x">\n<img src="https://example.com/x.png">\n正文'
        prepared = prepare_note_markdown(content)
        self.assertEqual(prepared.removed_local_images, ("./local.png",))
        self.assertIn("https://example.com/x.png", prepared.content)

    def test_reference_style_local_image_is_removed_without_rewriting_definition(self):
        content = "正文\n![截图][local]\n[local]: ./secret.png\n"
        prepared = prepare_note_markdown(content)
        self.assertEqual(prepared.removed_local_images, ("./secret.png",))
        self.assertEqual(prepared.content, "正文\n\n[local]: ./secret.png\n")

    def test_reference_style_network_image_and_definition_are_preserved(self):
        content = "![截图][remote]\n[remote]: https://example.com/image.png\n"
        self.assertEqual(prepare_note_markdown(content).content, content)

    def test_shared_local_reference_definition_keeps_ordinary_link_working(self):
        content = "![shot][asset]\n[download][asset]\n[asset]: ./a.png\n"
        prepared = prepare_note_markdown(content)
        self.assertEqual(prepared.content, "\n[download][asset]\n[asset]: ./a.png\n")
        self.assertEqual(prepared.removed_local_images, ("./a.png",))

    def test_only_local_reference_image_is_empty_after_filtering(self):
        with self.assertRaisesRegex(ValueError, "empty after"):
            prepare_note_markdown("![shot][asset]\n[asset]: ./a.png\n")

    def test_balanced_parentheses_in_local_destination_are_removed_cleanly(self):
        prepared = prepare_note_markdown("before ![x](./a(1).png) after")
        self.assertEqual(prepared.content, "before  after")
        self.assertEqual(prepared.removed_local_images, ("./a(1).png",))

    def test_code_and_escaped_image_syntax_are_preserved(self):
        content = (
            "```md\n![fenced](./fenced.png)\n```\n"
            "`![inline](./inline.png)`\n"
            "\\![escaped](./escaped.png)\n"
            "正文"
        )
        prepared = prepare_note_markdown(content)
        self.assertEqual(prepared.content, content)
        self.assertEqual(prepared.removed_local_images, ())

    def test_html_image_inside_code_is_preserved(self):
        content = '`<img src="./inline.png">`\n```html\n<img src="./fenced.png">\n```'
        self.assertEqual(prepare_note_markdown(content).content, content)

    def test_html_src_does_not_confuse_data_src(self):
        network = '<img data-src="./lazy.png" src="https://example.com/real.png">'
        data_only = '<img data-src="./lazy.png">'
        self.assertEqual(prepare_note_markdown(network).content, network)
        self.assertEqual(prepare_note_markdown(data_only).content, data_only)

    def test_html_src_text_inside_another_attribute_is_not_an_attribute(self):
        network = (
            '<img alt="example src=./fake.png" '
            'src="https://example.com/real.png">'
        )
        no_src = '<img alt="example src=./fake.png">'
        self.assertEqual(prepare_note_markdown(network).content, network)
        self.assertEqual(prepare_note_markdown(no_src).content, no_src)

    def test_unquoted_html_src_preserves_urls_and_reports_complete_local_paths(self):
        network = "<img\nSRC=https://example.com/x.png alt=x>"
        self.assertEqual(prepare_note_markdown(network).content, network)

        for path in ("/tmp/a.png", "./relative.png"):
            with self.subTest(path=path):
                prepared = prepare_note_markdown(f"正文<img src={path}>")
                self.assertEqual(prepared.content, "正文")
                self.assertEqual(prepared.removed_local_images, (path,))

    def test_html_comment_is_preserved(self):
        content = '<!-- <img src="./example.png"> -->\n正文'
        prepared = prepare_note_markdown(content)
        self.assertEqual(prepared.content, content)
        self.assertEqual(prepared.removed_local_images, ())

    def test_plain_paths_and_links_are_not_treated_as_images(self):
        content = "路径 ./local.png 以及 [链接](./local.png)"
        self.assertEqual(prepare_note_markdown(content).content, content)

    def test_surrogate_and_empty_after_filtering_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "UTF-8"):
            prepare_note_markdown("bad \ud800")
        with self.assertRaisesRegex(ValueError, "empty after"):
            prepare_note_markdown("![x](./only.png)\n")


if __name__ == "__main__":
    unittest.main()
