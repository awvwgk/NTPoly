################################################################################
# Target file for a Mac computer.
# Unfortunately, installing on the mac is a bit tricky. The problem is that
# when you install SWIG, it might link against the wrong version of python.
# That's why I've included custom set variables for the python framework,
# include path, etc. These come from using Homebrew with default settings.
# You might need to adjust based on your brew path (in this case /usr/local)
# and the version of python you have installed.
set(CMAKE_SYSTEM_NAME Darwin)
set(CMAKE_C_COMPILER mpicc)
set(CMAKE_Fortran_COMPILER mpif90)
set(CMAKE_CXX_COMPILER mpicxx)
set(PYTHON_EXECUTABLE python2)
set(PYTHON_INCLUDE_DIRS /usr/local/Cellar/python/2.7.13_1/Frameworks/Python.framework/Versions/2.7/Headers)
set(PYTHON_INCLUDE_PATH /usr/local/Cellar/python/2.7.13_1/Frameworks/Python.framework/Headers/ /usr/local/lib/python2.7/site-packages/mpi4py/include)
set(PYTHON_LIBRARIES /usr/local/Cellar/python/2.7.13_1/Frameworks/Python.framework/Versions/2.7/lib/libpython2.7.dylib)

set(CXX_TOOLCHAINFLAGS "-O3 -openmp -framework Accelerate -lgomp")
#set(F_TOOLCHAINFLAGS "-O3 -cpp -fopenmp")
# Debug suggestions
set(F_TOOLCHAINFLAGS "-fbounds-check -O0 -fexternal-blas -framework Accelerate -cpp -fopenmp -Wall -DPURE=")