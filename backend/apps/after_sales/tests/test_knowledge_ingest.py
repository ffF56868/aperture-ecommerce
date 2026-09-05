from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from apps.after_sales.knowledge_ingest import KnowledgeIngestError, extract_uploaded_file


class KnowledgeIngestTests(SimpleTestCase):
    def test_txt_and_markdown_are_decoded_and_cleaned(self):
        for filename in ("rules.txt", "rules.md"):
            uploaded = SimpleUploadedFile(filename, b"\xef\xbb\xbf\xe9\x80\x80\xe8\xb4\xa7\xe8\xa7\x84\xe5\x88\x99\r\n\r\n")

            content, extension = extract_uploaded_file(uploaded)

            self.assertEqual(content, "退货规则")
            self.assertEqual(extension, filename.rsplit(".", 1)[1])

    def test_unknown_file_extension_is_rejected(self):
        uploaded = SimpleUploadedFile("rules.exe", b"not knowledge")

        with self.assertRaisesMessage(KnowledgeIngestError, "仅支持"):
            extract_uploaded_file(uploaded)
