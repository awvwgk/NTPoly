"""
A test suite for the different solvers.
"""
import unittest
import NTPolySwig as nt
import warnings
from scipy.sparse import csr_matrix
from scipy.io import mmread
from mpi4py import MPI
from helpers import result_file, log_file


# MPI global communicator.
comm = MPI.COMM_WORLD
warnings.filterwarnings(action="ignore", module="scipy",
                        message="^internal gelsd")


class TestSolvers(unittest.TestCase):
    '''A test class for the different kinds of solvers.'''
    from os.path import join
    from helpers import scratch_dir
    # First input file.
    input_file = join(scratch_dir, "input.mtx")
    # Second input file.
    input_file2 = join(scratch_dir, "input2.mtx")
    # Matrix to compare against.
    CheckMat = 0
    # Rank of the current process.
    my_rank = 0
    # Dimension of the matrices to test.
    mat_dim = 31

    @classmethod
    def setUpClass(self):
        from os import environ
        '''Set up all of the tests.'''
        rows = int(environ['PROCESS_ROWS'])
        columns = int(environ['PROCESS_COLUMNS'])
        slices = int(environ['PROCESS_SLICES'])
        nt.ConstructGlobalProcessGrid(rows, columns, slices)

    @classmethod
    def tearDownClass(self):
        '''Cleanup this test'''
        nt.DestructGlobalProcessGrid()

    def setUp(self):
        '''Set up all of the tests.'''
        # Rank of the current process.
        self.my_rank = comm.Get_rank()
        # Parameters for iterative solvers.
        self.isp = nt.SolverParameters()
        # Parameters for fixed solvers.
        self.fsp = nt.SolverParameters()
        self.fsp.SetVerbosity(True)
        self.isp.SetVerbosity(True)
        self.isp.SetMonitorConvergence(False)
        self.fsp.SetMonitorConvergence(False)
        if nt.GetGlobalIsRoot():
            nt.ActivateLogger(log_file, True)

    def tearDown(self):
        from yaml import load, dump, SafeLoader
        from sys import stdout
        if nt.GetGlobalIsRoot():
            nt.DeactivateLogger()
            with open(log_file) as ifile:
                data = load(ifile, Loader=SafeLoader)
            dump(data, stdout)

    def create_matrix(self, SPD=None, scaled=None, diag_dom=None, rank=None,
                      add_gap=False):
        '''
        Create the test matrix with the following parameters.
        '''
        from scipy.sparse import rand, identity, csr_matrix
        from scipy.linalg import eigh
        from numpy import diag
        mat = rand(self.mat_dim, self.mat_dim, density=1.0)
        mat = mat + mat.T
        if SPD:
            mat = mat.T.dot(mat)
        if diag_dom:
            identity_matrix = identity(self.mat_dim)
            mat = mat + identity_matrix * self.mat_dim
        if scaled:
            mat = (1.0 / self.mat_dim) * mat
        if rank:
            mat = mat[rank:].dot(mat[rank:].T)
        if add_gap:
            w, v = eigh(mat.todense())
            gap = (w[-1] - w[0]) / 2.0
            w[int(self.mat_dim/2):] += gap
            mat = v.T.dot(diag(w).dot(v))
            mat = csr_matrix(mat)

        return csr_matrix(mat)

    def write_matrix(self, mat, file_name):
        from scipy.io import mmwrite
        if self.my_rank == 0:
            mmwrite(file_name, csr_matrix(mat))
        comm.barrier()

    def check_result(self):
        '''Compare two computed matrices.'''
        from helpers import THRESHOLD
        from scipy.sparse.linalg import norm
        normval = 0
        relative_error = 0
        if (self.my_rank == 0):
            ResultMat = mmread(result_file)
            normval = abs(norm(self.CheckMat - ResultMat))
            relative_error = normval / norm(self.CheckMat)
            print("\nNorm:", normval)
            print("Relative_Error:", relative_error)
        global_error = comm.bcast(relative_error, root=0)
        self.assertLessEqual(global_error, THRESHOLD)

    def check_diag(self):
        '''Compare two diagonal matrices.'''
        from helpers import THRESHOLD
        from numpy.linalg import norm as normd
        from scipy.sparse.linalg import norm
        from numpy import diag, sort
        normval = 0
        relative_error = 0
        if (self.my_rank == 0):
            ResultMat = sort(diag(mmread(result_file).todense()))
            CheckDiag = sort(diag(self.CheckMat.todense()))
            normval = abs(normd(CheckDiag - ResultMat))
            relative_error = normval / norm(self.CheckMat)
            print("\nNorm:", normval)
            print("Relative_Error:", relative_error)
        global_error = comm.bcast(relative_error, root=0)
        self.assertLessEqual(global_error, THRESHOLD)

    def test_invert(self):
        '''Test routines to invert matrices.'''
        from scipy.sparse.linalg import inv
        from scipy.sparse import csc_matrix
        # Starting Matrix
        matrix1 = self.create_matrix()
        self.write_matrix(matrix1, self.input_file)

        # Check Matrix
        self.CheckMat = inv(csc_matrix(matrix1))

        # Result Matrix
        overlap_matrix = nt.Matrix_ps(self.input_file, False)
        inverse_matrix = nt.Matrix_ps(self.mat_dim)
        permutation = nt.Permutation(overlap_matrix.GetLogicalDimension())
        permutation.SetRandomPermutation()
        self.isp.SetLoadBalance(permutation)

        nt.InverseSolvers.Invert(overlap_matrix, inverse_matrix, self.isp)

        inverse_matrix.WriteToMatrixMarket(result_file)
        comm.barrier()

        self.check_result()

    def test_denseinvert(self):
        '''Test routines to invert matrices.'''
        from scipy.sparse.linalg import inv
        from scipy.sparse import csc_matrix
        # Starting Matrix
        matrix1 = self.create_matrix()
        self.write_matrix(matrix1, self.input_file)

        # Check Matrix
        self.CheckMat = inv(csc_matrix(matrix1))

        # Result Matrix
        overlap_matrix = nt.Matrix_ps(self.input_file, False)
        inverse_matrix = nt.Matrix_ps(self.mat_dim)

        nt.InverseSolvers.DenseInvert(overlap_matrix, inverse_matrix, self.isp)

        inverse_matrix.WriteToMatrixMarket(result_file)
        comm.barrier()

        self.check_result()

    def test_pseudoinverse(self):
        '''Test routines to compute the pseudoinverse of matrices.'''
        from scipy.linalg import pinv
        # Starting Matrix.
        matrix1 = self.create_matrix(rank=int(self.mat_dim / 2))
        self.write_matrix(matrix1, self.input_file)

        # Check Matrix
        self.CheckMat = csr_matrix(pinv(matrix1.todense()))

        # Result Matrix
        overlap_matrix = nt.Matrix_ps(self.input_file, False)
        inverse_matrix = nt.Matrix_ps(self.mat_dim)
        permutation = nt.Permutation(overlap_matrix.GetLogicalDimension())
        permutation.SetRandomPermutation()
        self.isp.SetLoadBalance(permutation)

        nt.InverseSolvers.PseudoInverse(overlap_matrix, inverse_matrix,
                                        self.isp)

        inverse_matrix.WriteToMatrixMarket(result_file)
        comm.barrier()

        self.check_result()

    def test_inversesquareroot(self):
        '''Test routines to compute the inverse square root of matrices.'''
        from scipy.linalg import funm
        from numpy import sqrt
        # Starting Matrix. Care taken to make sure eigenvalues are positive.
        matrix1 = self.create_matrix(SPD=True, diag_dom=True)
        self.write_matrix(matrix1, self.input_file)

        # Check Matrix
        dense_check = funm(matrix1.todense(), lambda x: 1.0 / sqrt(x))
        self.CheckMat = csr_matrix(dense_check)

        # Result Matrix
        overlap_matrix = nt.Matrix_ps(self.input_file, False)
        inverse_matrix = nt.Matrix_ps(self.mat_dim)
        permutation = nt.Permutation(overlap_matrix.GetLogicalDimension())
        permutation.SetRandomPermutation()
        self.isp.SetLoadBalance(permutation)
        nt.SquareRootSolvers.InverseSquareRoot(overlap_matrix, inverse_matrix,
                                               self.isp)
        inverse_matrix.WriteToMatrixMarket(result_file)
        comm.barrier()

        self.check_result()

    def test_denseinversesquareroot(self):
        '''Test routines to compute the inverse square root of matrices.'''
        from scipy.linalg import funm
        from numpy import sqrt
        # Starting Matrix. Care taken to make sure eigenvalues are positive.
        matrix1 = self.create_matrix(SPD=True, diag_dom=True)
        self.write_matrix(matrix1, self.input_file)

        # Check Matrix
        dense_check = funm(matrix1.todense(), lambda x: 1.0 / sqrt(x))
        self.CheckMat = csr_matrix(dense_check)

        # Result Matrix
        overlap_matrix = nt.Matrix_ps(self.input_file, False)
        inverse_matrix = nt.Matrix_ps(self.mat_dim)
        nt.SquareRootSolvers.DenseInverseSquareRoot(overlap_matrix,
                                                    inverse_matrix,
                                                    self.isp)
        inverse_matrix.WriteToMatrixMarket(result_file)
        comm.barrier()

        self.check_result()

    def test_squareroot(self):
        '''Test routines to compute the square root of matrices.'''
        from scipy.linalg import funm
        from numpy import sqrt
        # Starting Matrix. Care taken to make sure eigenvalues are positive.
        matrix1 = self.create_matrix(SPD=True)
        self.write_matrix(matrix1, self.input_file)

        # Check Matrix
        dense_check = funm(matrix1.todense(), lambda x: sqrt(x))
        self.CheckMat = csr_matrix(dense_check)

        # Result Matrix
        input_matrix = nt.Matrix_ps(self.input_file, False)
        root_matrix = nt.Matrix_ps(self.mat_dim)
        permutation = nt.Permutation(input_matrix.GetLogicalDimension())
        permutation.SetRandomPermutation()
        self.isp.SetLoadBalance(permutation)
        nt.SquareRootSolvers.SquareRoot(input_matrix, root_matrix, self.isp)
        root_matrix.WriteToMatrixMarket(result_file)
        comm.barrier()

        self.check_result()

    def test_densesquareroot(self):
        '''Test routines to compute the square root of matrices.'''
        from scipy.linalg import funm
        from numpy import sqrt
        # Starting Matrix. Care taken to make sure eigenvalues are positive.
        matrix1 = self.create_matrix(SPD=True)
        self.write_matrix(matrix1, self.input_file)

        # Check Matrix
        dense_check = funm(matrix1.todense(), lambda x: sqrt(x))
        self.CheckMat = csr_matrix(dense_check)

        # Result Matrix
        input_matrix = nt.Matrix_ps(self.input_file, False)
        root_matrix = nt.Matrix_ps(self.mat_dim)
        nt.SquareRootSolvers.DenseSquareRoot(input_matrix, root_matrix,
                                             self.isp)
        root_matrix.WriteToMatrixMarket(result_file)
        comm.barrier()

        self.check_result()

    def test_inverseroot(self):
        '''Test routines to compute  general matrix inverse root.'''
        from scipy.linalg import funm
        from numpy import power
        roots = [1, 2, 3, 4, 5, 6, 7, 8]
        for root in roots:
            print("Root:", root)
            # Starting Matrix. Care taken to make sure eigenvalues are
            # positive.
            matrix1 = self.create_matrix(diag_dom=True)
            self.write_matrix(matrix1, self.input_file)

            # Check Matrix
            dense_check = funm(matrix1.todense(),
                               lambda x: power(x, -1.0 / root))
            self.CheckMat = csr_matrix(dense_check)

            # Result Matrix
            input_matrix = nt.Matrix_ps(self.input_file, False)
            inverse_matrix = nt.Matrix_ps(self.mat_dim)
            permutation = nt.Permutation(input_matrix.GetLogicalDimension())
            permutation.SetRandomPermutation()
            self.isp.SetLoadBalance(permutation)
            nt.RootSolvers.ComputeInverseRoot(input_matrix, inverse_matrix,
                                              root, self.isp)
            inverse_matrix.WriteToMatrixMarket(result_file)
            comm.barrier()

            self.check_result()

    def test_root(self):
        '''Test routines to compute  general matrix root.'''
        from scipy.linalg import funm
        from numpy import power
        roots = [1, 2, 3, 4, 5, 6, 7, 8]
        for root in roots:
            print("Root", root)
            # Starting Matrix. Care taken to make sure eigenvalues are
            # positive.
            matrix1 = self.create_matrix(diag_dom=True)
            self.write_matrix(matrix1, self.input_file)

            # Check Matrix
            dense_check = funm(matrix1.todense(),
                               lambda x: power(x, 1.0 / root))
            self.CheckMat = csr_matrix(dense_check)

            # Result Matrix
            input_matrix = nt.Matrix_ps(self.input_file, False)
            inverse_matrix = nt.Matrix_ps(self.mat_dim)
            permutation = nt.Permutation(input_matrix.GetLogicalDimension())
            permutation.SetRandomPermutation()
            self.isp.SetLoadBalance(permutation)
            nt.RootSolvers.ComputeRoot(input_matrix, inverse_matrix,
                                       root, self.isp)
            inverse_matrix.WriteToMatrixMarket(result_file)
            comm.barrier()
            self.check_result()

    def test_signfunction(self):
        '''Test routines to compute the matrix sign function.'''
        from scipy.linalg import funm
        from numpy import sign
        # Starting Matrix
        matrix1 = self.create_matrix()
        self.write_matrix(matrix1, self.input_file)

        # Check Matrix
        dense_check = funm(matrix1.todense(), lambda x: sign(x))
        self.CheckMat = csr_matrix(dense_check)

        # Result Matrix
        input_matrix = nt.Matrix_ps(self.input_file, False)
        sign_matrix = nt.Matrix_ps(self.mat_dim)
        permutation = nt.Permutation(input_matrix.GetLogicalDimension())
        permutation.SetRandomPermutation()
        self.isp.SetLoadBalance(permutation)
        nt.SignSolvers.ComputeSign(input_matrix, sign_matrix, self.isp)
        sign_matrix.WriteToMatrixMarket(result_file)
        comm.barrier()

        self.check_result()

    def test_densesignfunction(self):
        '''Test routines to compute the matrix sign function.'''
        from scipy.linalg import funm
        from numpy import sign
        # Starting Matrix
        matrix1 = self.create_matrix()
        self.write_matrix(matrix1, self.input_file)

        # Check Matrix
        dense_check = funm(matrix1.todense(), lambda x: sign(x))
        self.CheckMat = csr_matrix(dense_check)

        # Result Matrix
        input_matrix = nt.Matrix_ps(self.input_file, False)
        sign_matrix = nt.Matrix_ps(self.mat_dim)
        nt.SignSolvers.ComputeDenseSign(input_matrix, sign_matrix, self.isp)
        sign_matrix.WriteToMatrixMarket(result_file)
        comm.barrier()

        self.check_result()

    def test_exponentialfunction(self):
        '''Test routines to compute the matrix exponential.'''
        from scipy.linalg import funm
        from numpy import exp
        # Starting Matrix
        matrix1 = 8 * self.create_matrix(scaled=True)
        self.write_matrix(matrix1, self.input_file)

        # Check Matrix
        dense_check = funm(matrix1.todense(), lambda x: exp(x))
        self.CheckMat = csr_matrix(dense_check)

        # Result Matrix
        input_matrix = nt.Matrix_ps(self.input_file, False)
        exp_matrix = nt.Matrix_ps(self.mat_dim)
        permutation = nt.Permutation(input_matrix.GetLogicalDimension())
        permutation.SetRandomPermutation()
        self.fsp.SetLoadBalance(permutation)
        nt.ExponentialSolvers.ComputeExponential(input_matrix, exp_matrix,
                                                 self.fsp)
        exp_matrix.WriteToMatrixMarket(result_file)
        comm.barrier()

        self.check_result()

    def test_denseexponential(self):
        '''Test routines to compute the matrix exponential.'''
        from scipy.linalg import funm
        from numpy import exp
        # Starting Matrix
        matrix1 = 8 * self.create_matrix(scaled=True)
        self.write_matrix(matrix1, self.input_file)

        # Check Matrix
        dense_check = funm(matrix1.todense(), lambda x: exp(x))
        self.CheckMat = csr_matrix(dense_check)

        # Result Matrix
        input_matrix = nt.Matrix_ps(self.input_file, False)
        exp_matrix = nt.Matrix_ps(self.mat_dim)
        nt.ExponentialSolvers.ComputeDenseExponential(input_matrix,
                                                      exp_matrix,
                                                      self.fsp)
        exp_matrix.WriteToMatrixMarket(result_file)
        comm.barrier()

        self.check_result()

    def test_exponentialpade(self):
        '''
        Test routines to compute the matrix exponential using the pade method.
        '''
        from scipy.linalg import funm
        from numpy import exp
        # Starting Matrix
        matrix1 = 8 * self.create_matrix(scaled=True)
        self.write_matrix(matrix1, self.input_file)

        # Check Matrix
        dense_check = funm(matrix1.todense(), lambda x: exp(x))
        self.CheckMat = csr_matrix(dense_check)

        # Result Matrix
        input_matrix = nt.Matrix_ps(self.input_file, False)
        exp_matrix = nt.Matrix_ps(self.mat_dim)
        permutation = nt.Permutation(input_matrix.GetLogicalDimension())
        permutation.SetRandomPermutation()
        self.isp.SetLoadBalance(permutation)
        nt.ExponentialSolvers.ComputeExponentialPade(input_matrix, exp_matrix,
                                                     self.isp)
        exp_matrix.WriteToMatrixMarket(result_file)
        comm.barrier()

        self.check_result()

    def test_logarithmfunction(self):
        '''Test routines to compute the matrix logarithm.'''
        from scipy.linalg import funm
        from numpy import log
        # Starting Matrix. Care taken to make sure eigenvalues are positive.
        matrix1 = self.create_matrix(scaled=True, diag_dom=True)
        self.write_matrix(matrix1, self.input_file)

        # Check Matrix
        dense_check = funm(matrix1.todense(), lambda x: log(x))
        self.CheckMat = csr_matrix(dense_check)

        # Result Matrix
        input_matrix = nt.Matrix_ps(self.input_file, False)
        log_matrix = nt.Matrix_ps(self.mat_dim)
        permutation = nt.Permutation(input_matrix.GetLogicalDimension())
        permutation.SetRandomPermutation()
        self.fsp.SetLoadBalance(permutation)
        nt.ExponentialSolvers.ComputeLogarithm(input_matrix, log_matrix,
                                               self.fsp)
        log_matrix.WriteToMatrixMarket(result_file)
        comm.barrier()

        self.check_result()

    def test_denselogarithm(self):
        '''Test routines to compute the matrix logarithm.'''
        from scipy.linalg import funm
        from numpy import log
        # Starting Matrix. Care taken to make sure eigenvalues are positive.
        matrix1 = self.create_matrix(scaled=True, diag_dom=True)
        self.write_matrix(matrix1, self.input_file)

        # Check Matrix
        dense_check = funm(matrix1.todense(), lambda x: log(x))
        self.CheckMat = csr_matrix(dense_check)

        # Result Matrix
        input_matrix = nt.Matrix_ps(self.input_file, False)
        log_matrix = nt.Matrix_ps(self.mat_dim)
        nt.ExponentialSolvers.ComputeDenseLogarithm(input_matrix, log_matrix,
                                                    self.fsp)
        log_matrix.WriteToMatrixMarket(result_file)
        comm.barrier()

        self.check_result()

    def test_exponentialround(self):
        '''
        Test routines to compute the matrix exponential using a round
        trip calculation.
        '''
        matrix1 = 0.125 * self.create_matrix(scaled=True)
        self.write_matrix(matrix1, self.input_file)

        # Check Matrix
        self.CheckMat = csr_matrix(matrix1)

        # Result Matrix
        input_matrix = nt.Matrix_ps(self.input_file, False)
        exp_matrix = nt.Matrix_ps(self.mat_dim)
        round_matrix = nt.Matrix_ps(self.mat_dim)
        nt.ExponentialSolvers.ComputeExponential(input_matrix, exp_matrix,
                                                 self.fsp)
        nt.ExponentialSolvers.ComputeLogarithm(exp_matrix, round_matrix,
                                               self.fsp)
        round_matrix.WriteToMatrixMarket(result_file)
        comm.barrier()

        self.check_result()

    def test_sinfunction(self):
        '''Test routines to compute the matrix sine.'''
        from scipy.linalg import funm
        from numpy import sin
        # Starting Matrix
        matrix1 = self.create_matrix()
        self.write_matrix(matrix1, self.input_file)

        # Check Matrix
        dense_check = funm(matrix1.todense(), lambda x: sin(x))
        self.CheckMat = csr_matrix(dense_check)

        # Result Matrix
        input_matrix = nt.Matrix_ps(self.input_file, False)
        sin_matrix = nt.Matrix_ps(self.mat_dim)
        permutation = nt.Permutation(input_matrix.GetLogicalDimension())
        permutation.SetRandomPermutation()
        self.fsp.SetLoadBalance(permutation)
        nt.TrigonometrySolvers.Sine(input_matrix, sin_matrix, self.fsp)
        sin_matrix.WriteToMatrixMarket(result_file)
        comm.barrier()

        self.check_result()

    def test_densesinfunction(self):
        '''Test routines to compute the matrix sine.'''
        from scipy.linalg import funm
        from numpy import sin
        # Starting Matrix
        matrix1 = self.create_matrix()
        self.write_matrix(matrix1, self.input_file)

        # Check Matrix
        dense_check = funm(matrix1.todense(), lambda x: sin(x))
        self.CheckMat = csr_matrix(dense_check)

        # Result Matrix
        input_matrix = nt.Matrix_ps(self.input_file, False)
        sin_matrix = nt.Matrix_ps(self.mat_dim)
        nt.TrigonometrySolvers.DenseSine(input_matrix, sin_matrix, self.fsp)
        sin_matrix.WriteToMatrixMarket(result_file)
        comm.barrier()

        self.check_result()

    def test_cosfunction(self):
        '''Test routines to compute the matrix cosine.'''
        from scipy.linalg import funm
        from numpy import cos
        # Starting Matrix
        matrix1 = self.create_matrix()
        self.write_matrix(matrix1, self.input_file)

        # Check Matrix
        dense_check = funm(matrix1.todense(), lambda x: cos(x))
        self.CheckMat = csr_matrix(dense_check)

        # Result Matrix
        input_matrix = nt.Matrix_ps(self.input_file, False)
        cos_matrix = nt.Matrix_ps(self.mat_dim)
        permutation = nt.Permutation(input_matrix.GetLogicalDimension())
        permutation.SetRandomPermutation()
        self.fsp.SetLoadBalance(permutation)
        nt.TrigonometrySolvers.Cosine(input_matrix, cos_matrix, self.fsp)
        cos_matrix.WriteToMatrixMarket(result_file)
        comm.barrier()

        self.check_result()

    def test_densecosfunction(self):
        '''Test routines to compute the matrix cosine.'''
        from scipy.linalg import funm
        from numpy import cos
        # Starting Matrix
        matrix1 = self.create_matrix()
        self.write_matrix(matrix1, self.input_file)

        # Check Matrix
        dense_check = funm(matrix1.todense(), lambda x: cos(x))
        self.CheckMat = csr_matrix(dense_check)

        # Result Matrix
        input_matrix = nt.Matrix_ps(self.input_file, False)
        cos_matrix = nt.Matrix_ps(self.mat_dim)
        nt.TrigonometrySolvers.DenseCosine(input_matrix, cos_matrix, self.fsp)
        cos_matrix.WriteToMatrixMarket(result_file)
        comm.barrier()

        self.check_result()

    def test_hornerfunction(self):
        '''
        Test routines to compute a matrix polynomial using horner's
        method.
        '''
        from numpy.linalg import eigh
        from numpy import diag, dot
        # Coefficients of the polynomial
        coef = [1.0, 0.5, 0.25, 0.125, 0.0625, 0.03125, 0.015625]

        # Starting Matrix
        matrix1 = self.create_matrix(scaled=True)
        self.write_matrix(matrix1, self.input_file)

        # Check Matrix
        val, vec = eigh(matrix1.todense())
        for i in range(0, len(val)):
            temp = val[i]
            val[i] = 0
            for j in range(0, len(coef)):
                val[i] = val[i] + coef[j] * (temp**j)
        temp_poly = dot(dot(vec, diag(val)), vec.getH())
        self.CheckMat = csr_matrix(temp_poly)

        # Result Matrix
        input_matrix = nt.Matrix_ps(self.input_file, False)
        poly_matrix = nt.Matrix_ps(self.mat_dim)

        polynomial = nt.Polynomial(len(coef))
        for j in range(0, len(coef)):
            polynomial.SetCoefficient(j, coef[j])

        permutation = nt.Permutation(input_matrix.GetLogicalDimension())
        permutation.SetRandomPermutation()
        self.fsp.SetLoadBalance(permutation)
        polynomial.HornerCompute(input_matrix, poly_matrix, self.fsp)
        poly_matrix.WriteToMatrixMarket(result_file)
        comm.barrier()

        self.check_result()

    def test_patersonstockmeyerfunction(self):
        '''Test routines to compute a matrix polynomial using the paterson
        stockmeyer method.'''
        from numpy.linalg import eigh
        from numpy import diag, dot
        # Coefficients of the polynomial
        coef = [1.0, 0.5, 0.25, 0.125, 0.0625, 0.03125, 0.015625]

        # Starting Matrix
        matrix1 = self.create_matrix(scaled=True)
        self.write_matrix(matrix1, self.input_file)

        # Check Matrix
        val, vec = eigh(matrix1.todense())
        for i in range(0, len(val)):
            temp = val[i]
            val[i] = 0
            for j in range(0, len(coef)):
                val[i] = val[i] + coef[j] * (temp**j)
        temp_poly = dot(dot(vec, diag(val)), vec.getH())
        self.CheckMat = csr_matrix(temp_poly)

        # Result Matrix
        input_matrix = nt.Matrix_ps(self.input_file, False)
        poly_matrix = nt.Matrix_ps(self.mat_dim)

        polynomial = nt.Polynomial(len(coef))
        for j in range(0, len(coef)):
            polynomial.SetCoefficient(j, coef[j])

        permutation = nt.Permutation(input_matrix.GetLogicalDimension())
        permutation.SetRandomPermutation()
        self.fsp.SetLoadBalance(permutation)
        polynomial.PatersonStockmeyerCompute(input_matrix, poly_matrix,
                                             self.fsp)
        poly_matrix.WriteToMatrixMarket(result_file)
        comm.barrier()

        self.check_result()

    def test_chebyshevfunction(self):
        '''Test routines to compute using Chebyshev polynomials.'''
        from scipy.linalg import funm
        from numpy.polynomial.chebyshev import chebfit, chebval
        from numpy import cos, linspace, sin
        # Starting Matrix
        matrix1 = self.create_matrix(scaled=True)
        self.write_matrix(matrix1, self.input_file)

        # Function
        x = linspace(-1.0, 1.0, 200)
        y = [cos(i) + sin(i) for i in x]
        coef = chebfit(x, y, 10)

        # Check Matrix
        dense_check = funm(matrix1.todense(), lambda x: chebval(x, coef))
        self.CheckMat = csr_matrix(dense_check)

        # Result Matrix
        input_matrix = nt.Matrix_ps(self.input_file, False)
        poly_matrix = nt.Matrix_ps(self.mat_dim)

        polynomial = nt.ChebyshevPolynomial(len(coef))
        for j in range(0, len(coef)):
            polynomial.SetCoefficient(j, coef[j])

        permutation = nt.Permutation(input_matrix.GetLogicalDimension())
        permutation.SetRandomPermutation()
        self.fsp.SetLoadBalance(permutation)
        polynomial.Compute(input_matrix, poly_matrix, self.fsp)
        poly_matrix.WriteToMatrixMarket(result_file)
        comm.barrier()

        self.check_result()

    def test_recursivechebyshevfunction(self):
        '''Test routines to compute using Chebyshev polynomials
        recursively.'''
        from scipy.linalg import funm
        from numpy.polynomial.chebyshev import chebfit, chebval
        from numpy import exp, linspace
        # Starting Matrix
        matrix1 = self.create_matrix(scaled=True)
        self.write_matrix(matrix1, self.input_file)

        # Function
        x = linspace(-1.0, 1.0, 200)
        y = [exp(i) for i in x]
        coef = chebfit(x, y, 16 - 1)

        # Check Matrix
        dense_check = funm(matrix1.todense(), lambda x: chebval(x, coef))
        self.CheckMat = csr_matrix(dense_check)

        # Result Matrix
        input_matrix = nt.Matrix_ps(self.input_file, False)
        poly_matrix = nt.Matrix_ps(self.mat_dim)

        polynomial = nt.ChebyshevPolynomial(len(coef))
        for j in range(0, len(coef)):
            polynomial.SetCoefficient(j, coef[j])

        permutation = nt.Permutation(input_matrix.GetLogicalDimension())
        permutation.SetRandomPermutation()
        self.fsp.SetLoadBalance(permutation)
        polynomial.ComputeFactorized(input_matrix, poly_matrix, self.fsp)
        poly_matrix.WriteToMatrixMarket(result_file)
        comm.barrier()

        self.check_result()

    def test_cgsolve(self):
        '''Test routines to solve general matrix equations with CG.'''
        from scipy.sparse.linalg import inv
        from scipy.sparse import csc_matrix
        # Starting Matrix
        A = self.create_matrix(SPD=True)
        B = self.create_matrix()
        self.write_matrix(A, self.input_file)
        self.write_matrix(B, self.input_file2)

        # Check Matrix
        Ainv = inv(csc_matrix(A))
        self.CheckMat = csr_matrix(Ainv.dot(B))

        # Result Matrix
        AMat = nt.Matrix_ps(self.input_file, False)
        XMat = nt.Matrix_ps(AMat.GetActualDimension())
        BMat = nt.Matrix_ps(self.input_file2, False)
        permutation = nt.Permutation(AMat.GetLogicalDimension())
        permutation.SetRandomPermutation()
        self.isp.SetLoadBalance(permutation)

        nt.LinearSolvers.CGSolver(AMat, XMat, BMat, self.isp)

        XMat.WriteToMatrixMarket(result_file)
        comm.barrier()

        self.check_result()

    def test_powermethod(self):
        '''Test routines to compute eigenvalues with the power method.'''
        from helpers import THRESHOLD
        from scipy.sparse.linalg import eigsh
        # Starting Matrix
        matrix1 = self.create_matrix()
        self.write_matrix(matrix1, self.input_file)

        # Result Matrix
        max_value = 0.0
        input_matrix = nt.Matrix_ps(self.input_file, False)
        max_value = nt.EigenBounds.PowerBounds(input_matrix, self.isp)
        comm.barrier()

        vals, vec = eigsh(matrix1, which="LM", k=1)
        relative_error = abs(max_value - vals[0])
        global_error = comm.bcast(relative_error, root=0)
        self.assertLessEqual(global_error, THRESHOLD)

    def test_hermitefunction(self):
        '''Test routines to compute using Hermite polynomials.'''
        from scipy.linalg import funm
        from numpy.polynomial.hermite import hermfit, hermval
        from numpy import cos, linspace, sin
        # Starting Matrix
        matrix1 = self.create_matrix(scaled=True)
        self.write_matrix(matrix1, self.input_file)

        # Function
        x = linspace(-1.0, 1.0, 200)
        y = [cos(i) + sin(i) for i in x]
        coef = hermfit(x, y, 10)

        # Check Matrix
        dense_check = funm(matrix1.todense(), lambda x: hermval(x, coef))
        self.CheckMat = csr_matrix(dense_check)

        # Result Matrix
        input_matrix = nt.Matrix_ps(self.input_file, False)
        poly_matrix = nt.Matrix_ps(self.mat_dim)

        polynomial = nt.HermitePolynomial(len(coef))
        for j in range(0, len(coef)):
            polynomial.SetCoefficient(j, coef[j])

        permutation = nt.Permutation(input_matrix.GetLogicalDimension())
        permutation.SetRandomPermutation()
        self.fsp.SetLoadBalance(permutation)
        polynomial.Compute(input_matrix, poly_matrix, self.fsp)
        poly_matrix.WriteToMatrixMarket(result_file)
        comm.barrier()

        self.check_result()

    def test_polarfunction(self):
        '''Test routines to compute the matrix polar decomposition.'''
        from scipy.linalg import polar
        # Starting Matrix
        matrix1 = self.create_matrix()
        self.write_matrix(matrix1, self.input_file)

        # Check Matrix
        dense_check_u, dense_check_h = polar(matrix1.todense())
        self.CheckMat = csr_matrix(dense_check_h)

        # Result Matrix
        input_matrix = nt.Matrix_ps(self.input_file, False)
        u_matrix = nt.Matrix_ps(self.mat_dim)
        h_matrix = nt.Matrix_ps(self.mat_dim)
        permutation = nt.Permutation(input_matrix.GetLogicalDimension())
        permutation.SetRandomPermutation()
        self.isp.SetLoadBalance(permutation)
        nt.SignSolvers.ComputePolarDecomposition(input_matrix, u_matrix,
                                                 h_matrix, self.isp)
        h_matrix.WriteToMatrixMarket(result_file)
        comm.barrier()

        self.check_result()

        comm.barrier()
        self.CheckMat = csr_matrix(dense_check_u)
        u_matrix.WriteToMatrixMarket(result_file)

        self.check_result()

    def test_eigendecomposition(self):
        '''Test routines to compute eigendecomposition of matrices.'''
        from scipy.linalg import eigh
        from scipy.sparse import csc_matrix, diags
        # Starting Matrix
        matrix1 = self.create_matrix()
        self.write_matrix(matrix1, self.input_file)

        # Check Matrix
        vals, vecs = eigh(matrix1.todense())

        # Result Matrix
        matrix = nt.Matrix_ps(self.input_file, False)
        vec_matrix = nt.Matrix_ps(self.mat_dim)
        val_matrix = nt.Matrix_ps(self.mat_dim)

        nt.EigenSolvers.EigenDecomposition(matrix, val_matrix, self.mat_dim,
                                           vec_matrix, self.isp)

        # Check the eigenvalues
        val_matrix.WriteToMatrixMarket(result_file)
        self.CheckMat = csc_matrix(diags(vals))
        comm.barrier()
        self.check_result()

        # Check the eigenvectors
        reconstructed = nt.Matrix_ps(self.mat_dim)
        temp = nt.Matrix_ps(self.mat_dim)
        vec_matrix_t = nt.Matrix_ps(self.mat_dim)
        memory_pool = nt.PMatrixMemoryPool(matrix)
        temp.Gemm(vec_matrix, val_matrix, memory_pool)
        vec_matrix_t.Transpose(vec_matrix)
        vec_matrix_t.Conjugate()
        reconstructed.Gemm(temp, vec_matrix_t, memory_pool)
        reconstructed.WriteToMatrixMarket(result_file)

        self.CheckMat = matrix1
        comm.barrier()
        self.check_result()

    def test_eigendecomposition_partial(self):
        '''Test routines to compute partial eigendecomposition of matrices.'''
        from scipy.linalg import eigh
        from scipy.sparse import csc_matrix, diags
        # Starting Matrix
        matrix1 = self.create_matrix()
        self.write_matrix(matrix1, self.input_file)
        nvals = int(self.mat_dim/2)

        # Check Matrix
        vals, vecs = eigh(matrix1.todense())

        # Result Matrix
        matrix = nt.Matrix_ps(self.input_file, False)
        vec_matrix = nt.Matrix_ps(self.mat_dim)
        val_matrix = nt.Matrix_ps(self.mat_dim)

        nt.EigenSolvers.EigenDecomposition(matrix, val_matrix, nvals,
                                           vec_matrix, self.isp)

        # Check the eigenvalues
        val_matrix.WriteToMatrixMarket(result_file)
        vals[nvals:] = 0
        self.CheckMat = csc_matrix(diags(vals))
        comm.barrier()
        self.check_result()

        # Check the eigenvectors
        reconstructed = nt.Matrix_ps(self.mat_dim)
        temp = nt.Matrix_ps(self.mat_dim)
        vec_matrix_t = nt.Matrix_ps(self.mat_dim)
        memory_pool = nt.PMatrixMemoryPool(matrix)
        temp.Gemm(vec_matrix, val_matrix, memory_pool)
        vec_matrix_t.Transpose(vec_matrix)
        vec_matrix_t.Conjugate()
        reconstructed.Gemm(temp, vec_matrix_t, memory_pool)
        reconstructed.WriteToMatrixMarket(result_file)

        self.CheckMat = csc_matrix((vecs*vals).dot(vecs.conj().T))
        comm.barrier()
        self.check_result()

    def test_eigendecomposition_novecs(self):
        '''Test routines to compute eigenvalues (only) of matrices.'''
        from scipy.linalg import eigh
        from scipy.sparse import csc_matrix, diags
        # Starting Matrix
        matrix1 = self.create_matrix()
        self.write_matrix(matrix1, self.input_file)
        nvals = int(self.mat_dim/2)

        # Check Matrix
        vals, _ = eigh(matrix1.todense())

        # Result Matrix
        matrix = nt.Matrix_ps(self.input_file, False)
        val_matrix = nt.Matrix_ps(self.mat_dim)

        nt.EigenSolvers.EigenValues(matrix, val_matrix, nvals, self.isp)

        # Check the eigenvalues
        val_matrix.WriteToMatrixMarket(result_file)
        vals[nvals:] = 0
        self.CheckMat = csc_matrix(diags(vals))
        comm.barrier()
        self.check_result()

    def test_svd(self):
        '''Test routines to compute the SVD of matrices.'''
        from scipy.linalg import svd
        from scipy.sparse import csc_matrix, diags
        # Starting Matrix
        matrix1 = self.create_matrix()
        self.write_matrix(matrix1, self.input_file)

        # Check Matrix
        u, s, vh = svd(matrix1.todense())

        # Result Matrix
        matrix = nt.Matrix_ps(self.input_file, False)
        left_matrix = nt.Matrix_ps(self.mat_dim)
        right_matrix = nt.Matrix_ps(self.mat_dim)
        val_matrix = nt.Matrix_ps(self.mat_dim)

        nt.EigenSolvers.SingularValueDecomposition(matrix, left_matrix,
                                                   right_matrix, val_matrix,
                                                   self.isp)

        # Check the singular values.
        val_matrix.WriteToMatrixMarket(result_file)
        self.CheckMat = csc_matrix(diags(sorted(s)))
        comm.barrier()
        self.check_result()

        # Check the singular vectors.
        reconstructed = nt.Matrix_ps(self.mat_dim)
        temp = nt.Matrix_ps(self.mat_dim)
        right_matrix_t = nt.Matrix_ps(self.mat_dim)
        right_matrix_t.Transpose(right_matrix)
        right_matrix_t.Conjugate()
        memory_pool = nt.PMatrixMemoryPool(matrix)
        temp.Gemm(left_matrix, val_matrix, memory_pool)
        reconstructed.Gemm(temp, right_matrix_t, memory_pool)
        reconstructed.WriteToMatrixMarket(result_file)

        self.CheckMat = matrix1
        comm.barrier()
        self.check_result()

    def test_estimategap(self):
        '''Test routines to estimate homo-lumo gap.'''
        from scipy.linalg import eigh
        # Starting Matrix
        H = self.create_matrix(add_gap=True)
        self.write_matrix(H, self.input_file)

        # Check Matrix
        vals, _ = eigh(H.todense())
        nel = int(self.mat_dim/2)
        gap_gold = vals[nel] - vals[nel - 1]
        cp = vals[nel - 1] + 0.5 * gap_gold

        # Compute
        Hmat = nt.Matrix_ps(self.input_file, False)
        Kmat = nt.Matrix_ps(Hmat.GetActualDimension())

        # Density Part
        ISQ = nt.Matrix_ps(Hmat.GetActualDimension())
        ISQ.FillIdentity()
        SRoutine = nt.DensityMatrixSolvers.TRS4
        _, _ = SRoutine(Hmat, ISQ, nel, Kmat, self.isp)

        # Estimate Driver
        gap = nt.EigenSolvers.EstimateGap(Hmat, Kmat, cp, self.isp)

        # Check the value. Threshold has to be lose because of degenerate
        # eigenvalues near the gap.
        threshold = 0.5
        relative_error = abs(gap_gold - gap)
        global_error = comm.bcast(relative_error, root=0)
        self.assertLessEqual(global_error, threshold)


class TestSolvers_r(TestSolvers):
    def test_cholesky(self):
        from scipy.linalg import cholesky
        from scipy.sparse import csr_matrix
        '''Test subroutine that computes the cholesky decomposition.'''
        # Starting Matrix
        matrix1 = self.create_matrix(SPD=True)
        self.write_matrix(matrix1, self.input_file)

        # Check Matrix
        dense_check = cholesky(matrix1.todense(), lower=True)
        self.CheckMat = csr_matrix(dense_check)

        # Result Matrix
        input_matrix = nt.Matrix_ps(self.input_file, False)

        cholesky_matrix = nt.Matrix_ps(self.mat_dim)
        nt.LinearSolvers.CholeskyDecomposition(input_matrix, cholesky_matrix,
                                               self.fsp)

        cholesky_matrix.WriteToMatrixMarket(result_file)
        comm.barrier()

        self.check_result()

    def test_pivotedcholesky(self):
        from scipy.sparse import csr_matrix
        from scipy.linalg import eigh
        from numpy import diag
        '''Test subroutine that computes the pivoted cholesky decomposition.'''

        rank = 8

        # Starting Matrix - make it semidefinite
        mat = self.create_matrix(SPD=True)
        vals, vecs = eigh(mat.todense())
        vals[rank:] = 0
        self.CheckMat = csr_matrix(vecs.dot(diag(vals)).dot(vecs.T))
        self.write_matrix(self.CheckMat, self.input_file)

        # Result Matrix
        A = nt.Matrix_ps(self.input_file, False)
        L = nt.Matrix_ps(self.mat_dim)
        LT = nt.Matrix_ps(self.mat_dim)
        LLT = nt.Matrix_ps(self.mat_dim)
        memory_pool = nt.PMatrixMemoryPool(A)

        # We compare after reconstructing the original matrix.
        nt.Analysis.PivotedCholeskyDecomposition(A, L, rank, self.fsp)
        LT.Transpose(L)
        LLT.Gemm(L, LT, memory_pool)

        LLT.WriteToMatrixMarket(result_file)
        comm.barrier()

        self.check_result()

    def test_reducedimension(self):
        '''Test routines to reduced the matrix dimension matrices.'''
        from scipy.linalg import eigh, norm
        from helpers import THRESHOLD

        # Starting Matrix
        matrix1 = self.create_matrix(add_gap=True)
        self.write_matrix(matrix1, self.input_file)
        dim = int(self.mat_dim/2)

        # Check Value
        w, _ = eigh(matrix1.todense())

        # Result Matrix
        inmat = nt.Matrix_ps(self.input_file, False)
        outmat = nt.Matrix_ps(dim)
        nt.Analysis.ReduceDimension(inmat, dim, outmat, self.isp)
        outmat.WriteToMatrixMarket(result_file)
        comm.barrier()
        ResultMat = mmread(result_file)
        w2, _ = eigh(ResultMat.todense())

        # Comparison
        relative_error = 0
        if (self.my_rank == 0):
            relative_error = norm(w[:dim] - w2)
        global_error = comm.bcast(relative_error, root=0)
        self.assertLessEqual(global_error, THRESHOLD)


class TestSolvers_c(TestSolvers):
    def create_matrix(self, SPD=None, scaled=None, diag_dom=None, rank=None,
                      add_gap=False):
        '''
        Create the test matrix with the following parameters.
        '''
        from scipy.sparse import rand, identity, csr_matrix
        from scipy.linalg import eigh
        from numpy import diag
        mat = rand(self.mat_dim, self.mat_dim, density=1.0)
        mat += 1j * rand(self.mat_dim, self.mat_dim, density=1.0)
        mat = mat + mat.getH()
        if SPD:
            mat = mat.getH().dot(mat)
        if diag_dom:
            identity_matrix = identity(self.mat_dim)
            mat = mat + identity_matrix * self.mat_dim
        if scaled:
            mat = (1.0 / self.mat_dim) * mat
        if rank:
            mat = mat[rank:].dot(mat[rank:].getH())
        if add_gap:
            w, v = eigh(mat.todense())
            gap = (w[-1] - w[0]) / 2.0
            w[int(self.mat_dim/2):] += gap
            mat = v.conj().T.dot(diag(w).dot(v))
            mat = csr_matrix(mat)

        return csr_matrix(mat)


if __name__ == '__main__':
    unittest.main()
