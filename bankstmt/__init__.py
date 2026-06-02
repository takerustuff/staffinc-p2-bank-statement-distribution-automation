"""Automated bank-statement distribution to financiers.

Pulls the latest statements from Drive (bank->entity folders), regroups them by
entity, compresses/splits them under the 25 MB email limit, and emails them as
direct attachments to each financier. Designed to run from a single trigger and
to repeat every month with zero manual file handling.
"""

__version__ = "1.0.0"
