docs/_build/html: docs/*.rst docs/*/*.rst docs/conf.py
	$(MAKE) -C docs html
