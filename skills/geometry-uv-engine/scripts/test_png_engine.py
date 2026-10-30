from pathlib import Path
import runpy

if __name__ == '__main__':
    test_path = Path(__file__).resolve().parents[2] / 'visual-resource-pipeline' / 'scripts' / 'test_png_engine.py'
    runpy.run_path(str(test_path), run_name='__main__')
