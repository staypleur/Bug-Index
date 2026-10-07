"""Optional installed-package smoke tests; CI installs the small runtime set explicitly."""
import importlib.util
import os
import subprocess
import sys

import pytest

from server.catalog import classify

PROGRAMS = [
    ('pandas', 'import pandas as pd; pd.DataFrame({"a": 1})'),
    ('pandas', 'import pandas as pd; pd.DataFrame({"a": [1], "b": [1,2]})'),
    ('pandas', 'import pandas as pd; pd.Series([1,2]).item()'),
    ('pandas', 'import pandas as pd; pd.DataFrame({"a": [1]}).insert(0, "a", [2])'),
    ('numpy', 'import numpy as np; np.split(np.arange(5), 2)'),
    ('numpy', 'import numpy as np; np.average([1,2], weights=[0,0])'),
    ('numpy', 'import numpy as np; np.pad(np.ones(2), 1, mode="nope")'),
    ('numpy', 'import numpy as np; np.histogram([1,2], bins=0)'),
]


@pytest.mark.parametrize('package,program', PROGRAMS)
def test_real_library_traceback(package, program):
    interpreter = os.environ.get('BUG_INDEX_LIBRARY_TEST_PYTHON', sys.executable)
    if interpreter == sys.executable and not importlib.util.find_spec(package):
        pytest.skip(f'{package} not installed in test interpreter')
    result = subprocess.run([interpreter, '-c', program], text=True, capture_output=True, timeout=30)
    assert result.returncode != 0, result.stdout
    classified = classify(result.stderr)
    assert classified is not None, result.stderr
    assert classified.get('package') == package, (classified['name'], result.stderr)
