from pathlib import Path


PUBLIC_DOCS = (
    "README.md",
    "README.en.md",
    "docs/index.md",
    "docs/index.en.md",
    "docs/cli-tree.md",
    "docs/cli-tree.en.md",
    "docs/certificate-storage.md",
    "docs/certificate-storage.en.md",
    "docs/quickstart.md",
    "docs/quickstart.en.md",
)


def test_mkdocs_material_renderer_and_docs_metadata_contract():
    mkdocs = Path("mkdocs.yml").read_text(encoding="utf-8")
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert "site_url: https://arch.gh.wzhecnu.cn/ChatDNS/" in mkdocs
    assert "name: material" in mkdocs
    assert "mkdocs-material>=9.5,<10.0" in pyproject
    assert "pymdownx.emoji" in mkdocs
    assert "material.extensions.emoji.twemoji" in mkdocs
    assert "material.extensions.emoji.to_svg" in mkdocs
    assert 'Homepage = "https://arch.gh.wzhecnu.cn/ChatDNS/"' in pyproject
    assert 'Documentation = "https://arch.gh.wzhecnu.cn/ChatDNS/"' in pyproject
    assert 'Repository = "https://github.com/ChatArch/ChatDNS"' in pyproject


def test_public_docs_have_tree_and_no_material_literals():
    required = [
        "chatdns",
        "├── --tree  # Print this registered command tree and exit.",
        "├── cert  # Manage Let's Encrypt certificates through DNS-01 validation.",
        "│   └── status [DOMAINS...]",
        "└── set [FULL-DOMAIN]",
    ]
    for rel in PUBLIC_DOCS:
        text = Path(rel).read_text(encoding="utf-8")
        assert ":material-" not in text, rel
        assert "template `hello`" not in text, rel
        assert "ChatDNS" in text, rel
    for rel in ("README.md", "README.en.md", "docs/cli-tree.md", "docs/cli-tree.en.md"):
        text = Path(rel).read_text(encoding="utf-8")
        for line in required:
            assert line in text, f"{rel} missing {line!r}"
