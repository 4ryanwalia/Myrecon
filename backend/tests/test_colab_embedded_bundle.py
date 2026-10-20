"""Run the generated extraction cell against an empty runtime directory."""
import hashlib
import json
import zipfile

from tools.build_colab_bundle import FILES, build


def test_notebook_extracts_embedded_bundle_without_upload(tmp_path):
    output = tmp_path / "output"
    archive = build(output, "Worker 01", "MyRecon CPU Worker 01.ipynb")
    notebook = json.loads((output / "MyRecon CPU Worker 01.ipynb").read_text())
    assert notebook["metadata"]["colab"]["name"] == "MyRecon CPU Worker 01.ipynb"
    source = next("".join(cell["source"]) for cell in notebook["cells"]
                  if cell["cell_type"] == "code" and "bundle_bytes =" in "".join(cell["source"]))
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    source = source.replace("/content/", runtime.as_posix() + "/")
    exec(compile(source, "embedded-bundle-cell", "exec"), {})
    extracted_zip = runtime / "myrecon-colab-worker.zip"
    assert hashlib.sha256(extracted_zip.read_bytes()).digest() == hashlib.sha256(archive.read_bytes()).digest()
    with zipfile.ZipFile(extracted_zip) as bundle:
        for name in FILES:
            assert (runtime / "myrecon-worker" / name).read_bytes() == bundle.read(name)
    assert all(not cell.get("outputs") for cell in notebook["cells"])
