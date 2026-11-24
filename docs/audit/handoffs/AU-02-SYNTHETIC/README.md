# AU-02 synthetic handoff demonstration

This fixture demonstrates a documentation-only revision sequence: `r1` is rejected in synthetic fixture data and `r2` carries that negative verdict forward while awaiting independent review. The validator checks report hashes, revision order, source-reference URL shape, secret canaries, and that archived reports are Markdown files.

Run from the repository root:

```sh
python scripts/validate_au02_handoff.py
python -m unittest discover -s tests -p test_au02_handoff.py -v
```

The PR and CI URLs in the fixture are placeholders used to exercise schema checks. The offline validator does not query GitHub, prove a remote commit or run exists, establish an independent reviewer decision, or make a local manifest immutable. Once published, each source revision can be referenced by its Git commit SHA; final independent review remains pending. The fixture contains no application code.

