"""Re-run all 155 + 29 original test bodies and final engineering tests."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import sys,unittest,shutil,json,importlib.util
from pathlib import Path
from src.paths import FINAL,save,now
from src.runtime import CORE


def load_local(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def main():
    load_local('final_fixture_helpers',FINAL/'tests/fixtures.py').install()
    import run_v3
    artifact=FINAL/'outputs/unit_artifacts';(artifact/'results').mkdir(parents=True,exist_ok=True);run_v3.OUT=artifact/'results'
    import test_v3,test_v31,test_v32,test_stage3
    test_v31.ROOT=artifact
    for name in ['cleaner.py','baseline_cleaner.py']:shutil.copyfile(CORE/name,artifact/name)
    old=unittest.defaultTestLoader.discover(str(CORE/'legacy/tests'),top_level_dir=str(CORE/'legacy'))
    for module in [test_v3,test_v31,test_v32]:old.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
    original_n=old.countTestCases();phase3=unittest.defaultTestLoader.loadTestsFromModule(test_stage3);phase3_n=phase3.countTestCases()
    test_final=load_local('final_engineering_tests',FINAL/'tests/test_final.py')
    final=unittest.defaultTestLoader.loadTestsFromModule(test_final);final_n=final.countTestCases()
    assert original_n==155 and phase3_n==29
    suite=unittest.TestSuite([old,phase3,final]);result=unittest.TextTestRunner(verbosity=2,stream=sys.stdout).run(suite)
    save(FINAL/'reports/test_results.json',dict(time_utc=now(),original_tests=original_n,phase3_tests=phase3_n,final_tests=final_n,total=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),success=result.wasSuccessful() and not result.skipped,
                fixture='Original training features with deterministic synthetic income for unit fixtures only; no real test labels shipped or read',original_test_bodies_edited=False))
    raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)


if __name__=='__main__':main()
