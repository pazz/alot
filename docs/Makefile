# Makefile for Sphinx documentation
#

# You can set these variables from the command line.
SPHINXOPTS    =
PYTHON        = python3
SPHINXBUILD   = $(PYTHON) -m sphinx
BUILDDIR      = build

CONFIG_OPTION_TABLES = source/configuration/alotrc_table source/configuration/accounts_table
COMMAND_OPTION_TABLES = source/usage/modes/bufferlist.rst \
			source/usage/modes/envelope.rst \
			source/usage/modes/global.rst \
			source/usage/modes/search.rst \
			source/usage/modes/taglist.rst \
			source/usage/modes/thread.rst


.PHONY: html man clean cleanall

html man: $(CONFIG_OPTION_TABLES) $(COMMAND_OPTION_TABLES)
	$(SPHINXBUILD) -b $@ -d $(BUILDDIR)/doctrees $(SPHINXOPTS) source $(BUILDDIR)/$@

$(COMMAND_OPTION_TABLES): ../alot/commands/__init__.py
	$(PYTHON) source/generate_commands.py

$(CONFIG_OPTION_TABLES): ../alot/defaults/alot.rc.spec
	$(PYTHON) source/generate_configs.py

clean:
	-$(RM) -rf $(BUILDDIR)/*

cleanall: clean
	-$(RM) -rf $(CONFIG_OPTION_TABLES) $(COMMAND_OPTION_TABLES)
