from setuptools import Extension
from numpy import get_include   # cimport numpy を使うため
import os

bezier_path = '../bezier/src/fortran/include'

kwargs = {"output_dir": "./build/output", "build_dir": "./build/"}


def get_ext():
    ext = []
    sources = [os.path.join("module", "MMath.pyx"), os.path.join("module", "MOptions.pyx"), os.path.join("module", "MParams.pyx"), \
               os.path.join("utils", "MLogger.py"), os.path.join("utils", "MBezierUtils.pyx"), os.path.join("utils", "MServiceUtils.pyx"), \
               os.path.join("mmd", "VmdData.pyx"), os.path.join("mmd", "VmdReader.py"), os.path.join("mmd", "PmxData.pyx"), os.path.join("mmd", "PmxReader.py"), \
               os.path.join("service", "ConvertMultiSplitService.py"), os.path.join("service", "ConvertMultiJoinService.py"), os.path.join("service", "ConvertParentService.py"), \
               os.path.join("service", "ConvertLegFKtoIKService.py"), os.path.join("service", "ConvertNoiseService.py"), os.path.join("service", "ConvertSmoothService.py")]
    # for path in glob.glob("*/**/*.pyx", recursive=True):
    #     if os.path.isfile(path):
    #         print(path)
    #         sources.append(path)
    # for path in glob.glob("*/**/*.py", recursive=True):
    #     if "__init__" not in path and os.path.isfile(path):
    #         sources.append(path)

    for source in sources:
        path = source.replace(os.sep, ".").replace(".pyx", "").replace(".py", "")
        print("%s -> %s" % (source, path))
        ext.append(Extension(path, sources=[source], include_dirs=['.', bezier_path, get_include()], define_macros=[("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION")]))
    
    return ext

# ext = [Extension("module.MMath", sources=["module/MMath.py"], include_dirs=['.', bezier_path, get_include()]), \
#        # Extension("module.MMath", sources=["module/MMath.py"], include_dirs=['.', bezier_path, get_include()], define_macros=[('CYTHON_TRACE', '1')]), \
#        Extension("module.MParams", sources=["module/MParams.py"], include_dirs=['.', bezier_path, get_include()]), \
#        Extension("module.MOptions", sources=["module/MOptions.py"], include_dirs=['.', bezier_path, get_include()]), \
#        Extension("utils.MBezierUtils", sources=["utils/MBezierUtils.py"], include_dirs=['.', bezier_path, get_include()]), \
#        Extension("utils.MLogger", sources=["utils/MLogger.py"], include_dirs=['.', bezier_path, get_include()]), \
#        # Extension("utils.MServiceUtils", sources=["utils/MServiceUtils.py"], include_dirs=['.', bezier_path, get_include()], define_macros=[('CYTHON_TRACE', '1')]), \
#        Extension("utils.MServiceUtils", sources=["utils/MServiceUtils.py"], include_dirs=['.', bezier_path, get_include()]), \
#        Extension("mmd.PmxData", sources=["mmd/PmxData.py"], include_dirs=['.', bezier_path, get_include()]), \
#        Extension("mmd.PmxReader", sources=["mmd/PmxReader.py"], include_dirs=['.', bezier_path, get_include()]), \
#        # Extension("mmd.VmdData", sources=["mmd/VmdData.py"], include_dirs=['.', bezier_path, get_include()], define_macros=[('CYTHON_TRACE', '1')]), \
#        Extension("mmd.VmdData", sources=["mmd/VmdData.py"], include_dirs=['.', bezier_path, get_include()]), \
#        Extension("mmd.VmdReader", sources=["mmd/VmdReader.py"], include_dirs=['.', bezier_path, get_include()]), \
#        # Extension("mmd.VpdReader", sources=["mmd/VpdReader.py"], include_dirs=['.', bezier_path, get_include()]), \
#        # Extension("mmd.VmdWriter", sources=["mmd/VmdWriter.py"], include_dirs=['.', bezier_path, get_include()]), \
#        # Extension("service.parts.MoveService", sources=["service/parts/MoveService.py"], include_dirs=['.', bezier_path, get_include()]), \
#        # Extension("service.parts.CameraService", sources=["service/parts/CameraService.py"], include_dirs=['.', bezier_path, get_include()]), \
#        # Extension("service.parts.MorphService", sources=["service/parts/MorphService.py"], include_dirs=['.', bezier_path, get_include()]), \
#        Extension("service.parts.StanceService", sources=["service/parts/StanceService.py"], include_dirs=['.', bezier_path, get_include()]), \
#        # Extension("service.parts.ArmAvoidanceService", sources=["service/parts/ArmAvoidanceService.py"], include_dirs=['.', bezier_path, get_include()], define_macros=[('CYTHON_TRACE', '1')]), \
#        Extension("service.parts.ArmAvoidanceService", sources=["service/parts/ArmAvoidanceService.py"], include_dirs=['.', bezier_path, get_include()]), \
#        Extension("service.parts.ArmAlignmentService", sources=["service/parts/ArmAlignmentService.py"], include_dirs=['.', bezier_path, get_include()]), \
#        Extension("service.SizingService", sources=["service/SizingService.py"], include_dirs=['.', bezier_path, get_include()]), \
#        # Extension("service.ConvertSmoothService", sources=["service/ConvertSmoothService.py"], include_dirs=['.', bezier_path, get_include()]), \
#        ]


