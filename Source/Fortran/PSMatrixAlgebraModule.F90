!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
!> A Module For Performing Distributed Sparse Matrix Algebra Operations.
MODULE PSMatrixAlgebraModule
  USE DataTypesModule, ONLY : NTREAL, MPINTREAL, NTCOMPLEX, MPINTCOMPLEX
  USE GemmTasksModule
  USE MatrixReduceModule, ONLY : ReduceHelper_t, ReduceAndComposeMatrixSizes, &
       & ReduceAndComposeMatrixData, ReduceAndComposeMatrixCleanup, &
       & ReduceAndSumMatrixSizes, ReduceAndSumMatrixData, &
       & ReduceAndSumMatrixCleanup, TestReduceSizeRequest, &
       & TestReduceInnerRequest, TestReduceDataRequest
  USE PMatrixMemoryPoolModule, ONLY : MatrixMemoryPool_p, &
       & CheckMemoryPoolValidity, DestructMatrixMemoryPool, &
       & ConstructMatrixMemoryPool
  USE PSMatrixModule, ONLY : Matrix_ps, ConstructEmptyMatrix, CopyMatrix, &
       & DestructMatrix, ConvertMatrixToComplex, ConjugateMatrix, &
       & MergeMatrixLocalBlocks, IsIdentity, TransposeMatrix, &
       & SplitMatrixToLocalBlocks
  USE SMatrixAlgebraModule, ONLY : MatrixMultiply, MatrixGrandSum, &
       & PairwiseMultiplyMatrix, IncrementMatrix, ScaleMatrix, &
       & MatrixColumnNorm, MatrixDiagonalScale
  USE SMatrixModule, ONLY : Matrix_lsr, Matrix_lsc, DestructMatrix, CopyMatrix,&
       & TransposeMatrix, ComposeMatrixColumns, MatrixToTripletList
  USE TripletListModule, ONLY : TripletList_r, TripletList_c, &
       & ConstructTripletList, AppendToTripletList, DestructTripletList, &
       & GetTripletAt
  USE TripletModule, ONLY : Triplet_r, Triplet_c
  USE NTMPIModule
  IMPLICIT NONE
  PRIVATE
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  PUBLIC :: MatrixSigma
  PUBLIC :: MatrixMultiply
  PUBLIC :: MatrixGrandSum
  PUBLIC :: PairwiseMultiplyMatrix
  PUBLIC :: MatrixNorm
  PUBLIC :: DotMatrix
  PUBLIC :: IncrementMatrix
  PUBLIC :: ScaleMatrix
  PUBLIC :: MatrixTrace
  PUBLIC :: SimilarityTransform
  PUBLIC :: MeasureAsymmetry
  PUBLIC :: SymmetrizeMatrix
  PUBLIC :: MatrixDiagonalScale
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  INTERFACE MatrixSigma
     MODULE PROCEDURE MatrixSigma_ps
  END INTERFACE MatrixSigma
  INTERFACE MatrixMultiply
     MODULE PROCEDURE MatrixMultiply_ps
  END INTERFACE MatrixMultiply
  INTERFACE MatrixGrandSum
     MODULE PROCEDURE MatrixGrandSum_psr
     MODULE PROCEDURE MatrixGrandSum_psc
  END INTERFACE MatrixGrandSum
  INTERFACE PairwiseMultiplyMatrix
     MODULE PROCEDURE PairwiseMultiplyMatrix_ps
  END INTERFACE PairwiseMultiplyMatrix
  INTERFACE MatrixNorm
     MODULE PROCEDURE MatrixNorm_ps
  END INTERFACE MatrixNorm
  INTERFACE DotMatrix
     MODULE PROCEDURE DotMatrix_psr
     MODULE PROCEDURE DotMatrix_psc
  END INTERFACE DotMatrix
  INTERFACE IncrementMatrix
     MODULE PROCEDURE IncrementMatrix_ps
  END INTERFACE IncrementMatrix
  INTERFACE ScaleMatrix
     MODULE PROCEDURE ScaleMatrix_psr
     MODULE PROCEDURE ScaleMatrix_psc
  END INTERFACE ScaleMatrix
  INTERFACE MatrixDiagonalScale
     MODULE PROCEDURE MatrixDiagonalScale_psr
     MODULE PROCEDURE MatrixDiagonalScale_psc
  END INTERFACE MatrixDiagonalScale
  INTERFACE MatrixTrace
     MODULE PROCEDURE MatrixTrace_psr
  END INTERFACE MatrixTrace
CONTAINS!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  !> Compute sigma for the inversion method.
  !> See \cite ozaki2001efficient for details.
  SUBROUTINE MatrixSigma_ps(this, sigma_value)
    !> The matrix to compute the sigma value of.
    TYPE(Matrix_ps), INTENT(IN) :: this
    !> Sigma
    REAL(NTREAL), INTENT(OUT) :: sigma_value
    !! Local Data
    REAL(NTREAL), DIMENSION(:), ALLOCATABLE :: column_sigma_contribution
    !! Counters/Temporary
    INTEGER :: II, JJ
    TYPE(Matrix_lsr) :: merged_local_data_r
    TYPE(Matrix_lsc) :: merged_local_data_c
    INTEGER :: ierr

    IF (this%is_complex) THEN
#define LMAT merged_local_data_c
#include "distributed_algebra_includes/MatrixSigma.f90"
#undef LMAT
    ELSE
#define LMAT merged_local_data_r
#include "distributed_algebra_includes/MatrixSigma.f90"
#undef LMAT
    ENDIF
  END SUBROUTINE MatrixSigma_ps
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  !> Multiply two matrices together, and add to the third.
  !> C := alpha*matA*matB+ beta*matC
  SUBROUTINE MatrixMultiply_ps(matA, matB, matC, alpha_in, beta_in, &
       & threshold_in, memory_pool_in)
    !> Matrix A.
    TYPE(Matrix_ps), INTENT(IN)        :: matA
    !> Matrix B.
    TYPE(Matrix_ps), INTENT(IN)        :: matB
    !> matC = alpha*matA*matB + beta*matC
    TYPE(Matrix_ps), INTENT(INOUT)     :: matC
    !> Scales the multiplication
    REAL(NTREAL), OPTIONAL, INTENT(IN) :: alpha_in
    !> Scales matrix we sum on to.
    REAL(NTREAL), OPTIONAL, INTENT(IN) :: beta_in
    !> For flushing values to zero.
    REAL(NTREAL), OPTIONAL, INTENT(IN) :: threshold_in
    !> A memory pool for the calculation.
    TYPE(MatrixMemoryPool_p), OPTIONAL, INTENT(INOUT) :: memory_pool_in
    !! Local Versions of Optional Parameter
    TYPE(Matrix_ps) :: matAConverted
    TYPE(Matrix_ps) :: matBConverted
    REAL(NTREAL) :: alpha
    REAL(NTREAL) :: beta
    REAL(NTREAL) :: threshold
    TYPE(MatrixMemoryPool_p) :: memory_pool

    !! Handle the optional parameters
    IF (.NOT. PRESENT(alpha_in)) THEN
       alpha = 1.0_NTREAL
    ELSE
       alpha = alpha_in
    END IF
    IF (.NOT. PRESENT(beta_in)) THEN
       beta = 0.0_NTREAL
    ELSE
       beta = beta_in
    END IF
    IF (.NOT. PRESENT(threshold_in)) THEN
       threshold = 0.0_NTREAL
    ELSE
       threshold = threshold_in
    END IF

    !! Setup Memory Pool
    IF (PRESENT(memory_pool_in)) THEN
       IF (matA%is_complex) THEN
          IF (.NOT. CheckMemoryPoolValidity(memory_pool_in, matA)) THEN
             CALL DestructMatrixMemoryPool(memory_pool_in)
             CALL ConstructMatrixMemoryPool(memory_pool_in, matA)
          END IF
       ELSE
          IF (.NOT. CheckMemoryPoolValidity(memory_pool_in, matB)) THEN
             CALL DestructMatrixMemoryPool(memory_pool_in)
             CALL ConstructMatrixMemoryPool(memory_pool_in, matB)
          END IF
       END IF
    ELSE
       IF (matA%is_complex) THEN
          CALL ConstructMatrixMemoryPool(memory_pool, matA)
       ELSE
          CALL ConstructMatrixMemoryPool(memory_pool, matB)
       END IF
    END IF

    !! Perform Upcasting
    IF (matB%is_complex .AND. .NOT. matA%is_complex) THEN
       CALL ConvertMatrixToComplex(matA, matAConverted)
       IF (PRESENT(memory_pool_in)) THEN
          CALL MatrixMultiply_psc(matAConverted, matB, matC, alpha, beta, &
               & threshold, memory_pool_in)
       ELSE
          CALL MatrixMultiply_psc(matAConverted, matB, matC, alpha, beta, &
               & threshold, memory_pool)
       END IF
    ELSE IF (matA%is_complex .AND. .NOT. matB%is_complex) THEN
       CALL ConvertMatrixToComplex(matB, matBConverted)
       IF (PRESENT(memory_pool_in)) THEN
          CALL MatrixMultiply_psc(matA, matBConverted, matC, alpha, beta, &
               & threshold, memory_pool_in)
       ELSE
          CALL MatrixMultiply_psc(matA, matBConverted, matC, alpha, beta, &
               & threshold, memory_pool)
       END IF
    ELSE IF (matA%is_complex .AND. matB%is_complex) THEN
       IF (PRESENT(memory_pool_in)) THEN
          CALL MatrixMultiply_psc(matA, matB, matC, alpha, beta, &
               & threshold, memory_pool_in)
       ELSE
          CALL MatrixMultiply_psc(matA, matB, matC, alpha, beta, &
               & threshold, memory_pool)
       END IF
    ELSE
       IF (PRESENT(memory_pool_in)) THEN
          CALL MatrixMultiply_psr(matA, matB, matC, alpha, beta, &
               & threshold, memory_pool_in)
       ELSE
          CALL MatrixMultiply_psr(matA, matB, matC, alpha, beta, &
               & threshold, memory_pool)
       END IF
    END IF

    CALL DestructMatrixMemoryPool(memory_pool)
    CALL DestructMatrix(matAConverted)
    CALL DestructMatrix(matBConverted)

  END SUBROUTINE MatrixMultiply_ps
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  !> The actual implementation of matrix multiply is here. Takes the
  !> same parameters as the standard multiply, but nothing is optional.
  SUBROUTINE MatrixMultiply_psr(matA, matB, matC, alpha, beta, &
       & threshold, memory_pool)
    !! Parameters
    TYPE(Matrix_ps), INTENT(IN)    :: matA
    TYPE(Matrix_ps), INTENT(IN)    :: matB
    TYPE(Matrix_ps), INTENT(INOUT) :: matC
    REAL(NTREAL), INTENT(IN) :: alpha
    REAL(NTREAL), INTENT(IN) :: beta
    REAL(NTREAL), INTENT(IN) :: threshold
    TYPE(MatrixMemoryPool_p), INTENT(INOUT) :: memory_pool
    !! Temporary Matrices
    TYPE(Matrix_lsr), DIMENSION(:,:), ALLOCATABLE :: AdjacentABlocks
    TYPE(Matrix_lsr), DIMENSION(:), ALLOCATABLE :: LocalRowContribution
    TYPE(Matrix_lsr), DIMENSION(:), ALLOCATABLE :: GatheredRowContribution
    TYPE(Matrix_lsr), DIMENSION(:), ALLOCATABLE :: GatheredRowContributionT
    TYPE(Matrix_lsr), DIMENSION(:,:), ALLOCATABLE :: TransposedBBlocks
    TYPE(Matrix_lsr), DIMENSION(:), ALLOCATABLE :: LocalColumnContribution
    TYPE(Matrix_lsr), DIMENSION(:), ALLOCATABLE :: GatheredColumnContribution
    TYPE(Matrix_lsr), DIMENSION(:,:), ALLOCATABLE :: SliceContribution

#define LMAT local_data_r
#define MPGRID memory_pool%grid_r
#include "distributed_algebra_includes/MatrixMultiply.f90"
#undef LMAT
#undef MPGRID
  END SUBROUTINE MatrixMultiply_psr
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  !> The actual implementation of matrix multiply is here. Takes the
  !> same parameters as the standard multiply, but nothing is optional.
  SUBROUTINE MatrixMultiply_psc(matA, matB, matC, alpha, beta, &
       & threshold, memory_pool)
    !! Parameters
    TYPE(Matrix_ps), INTENT(IN)    :: matA
    TYPE(Matrix_ps), INTENT(IN)    :: matB
    TYPE(Matrix_ps), INTENT(INOUT) :: matC
    REAL(NTREAL), INTENT(IN) :: alpha
    REAL(NTREAL), INTENT(IN) :: beta
    REAL(NTREAL), INTENT(IN) :: threshold
    TYPE(MatrixMemoryPool_p), INTENT(INOUT) :: memory_pool
    !! Temporary Matrices
    TYPE(Matrix_lsc), DIMENSION(:,:), ALLOCATABLE :: AdjacentABlocks
    TYPE(Matrix_lsc), DIMENSION(:), ALLOCATABLE :: LocalRowContribution
    TYPE(Matrix_lsc), DIMENSION(:), ALLOCATABLE :: GatheredRowContribution
    TYPE(Matrix_lsc), DIMENSION(:), ALLOCATABLE :: GatheredRowContributionT
    TYPE(Matrix_lsc), DIMENSION(:,:), ALLOCATABLE :: TransposedBBlocks
    TYPE(Matrix_lsc), DIMENSION(:), ALLOCATABLE :: LocalColumnContribution
    TYPE(Matrix_lsc), DIMENSION(:), ALLOCATABLE :: GatheredColumnContribution
    TYPE(Matrix_lsc), DIMENSION(:,:), ALLOCATABLE :: SliceContribution

#define LMAT local_data_c
#define MPGRID memory_pool%grid_c
#include "distributed_algebra_includes/MatrixMultiply.f90"
#undef LMAT
#undef MPGRID
  END SUBROUTINE MatrixMultiply_psc
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  !> Sum up the elements in a matrix into a single value.
  SUBROUTINE MatrixGrandSum_psr(this, sum)
    !> The matrix to compute.
    TYPE(Matrix_ps), INTENT(IN)  :: this
    !> The sum of all elements.
    REAL(NTREAL), INTENT(OUT) :: sum
    !! Local Data
    INTEGER :: II, JJ
    REAL(NTREAL) :: temp_r
    COMPLEX(NTCOMPLEX) :: temp_c
    INTEGER :: ierr

#define MPIDATATYPE MPINTREAL
    IF (this%is_complex) THEN
#define TEMP temp_c
#define LMAT local_data_c
#include "distributed_algebra_includes/MatrixGrandSum.f90"
#undef LMAT
#undef TEMP
    ELSE
#define TEMP temp_r
#define LMAT local_data_r
#include "distributed_algebra_includes/MatrixGrandSum.f90"
#undef LMAT
#undef TEMP
    END IF
#undef MPIDATATYPE
  END SUBROUTINE MatrixGrandSum_psr
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  !> Sum up the elements in a matrix into a single value.
  SUBROUTINE MatrixGrandSum_psc(this, sum)
    !> The matrix to compute.
    TYPE(Matrix_ps), INTENT(IN)  :: this
    !> The sum of all elements.
    COMPLEX(NTCOMPLEX), INTENT(OUT) :: sum
    !! Local Data
    INTEGER :: II, JJ
    REAL(NTREAL) :: temp_r
    COMPLEX(NTCOMPLEX) :: temp_c
    INTEGER :: ierr

#define MPIDATATYPE MPINTCOMPLEX
    IF (this%is_complex) THEN
#define TEMP temp_c
#define LMAT local_data_c
#include "distributed_algebra_includes/MatrixGrandSum.f90"
#undef LMAT
#undef TEMP
    ELSE
#define TEMP temp_r
#define LMAT local_data_r
#include "distributed_algebra_includes/MatrixGrandSum.f90"
#undef LMAT
#undef TEMP
    END IF
#undef MPIDATATYPE
  END SUBROUTINE MatrixGrandSum_psc
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  !> Elementwise multiplication. C_ij = A_ij * B_ij.
  !> Also known as a Hadamard product.
  RECURSIVE SUBROUTINE PairwiseMultiplyMatrix_ps(matA, matB, matC)
    !> Matrix A.
    TYPE(Matrix_ps), INTENT(IN)  :: matA
    !> Matrix B.
    TYPE(Matrix_ps), INTENT(IN)  :: matB
    !> matC = MatA mult MatB.
    TYPE(Matrix_ps), INTENT(INOUT)  :: matC
    !! Local Data
    TYPE(Matrix_ps) :: converted_matrix
    INTEGER :: II, JJ

    IF (matA%is_complex .AND. .NOT. matB%is_complex) THEN
       CALL ConvertMatrixToComplex(matB, converted_matrix)
       CALL PairwiseMultiplyMatrix(matA, converted_matrix, matC)
       CALL DestructMatrix(converted_matrix)
    ELSE IF (.NOT. matA%is_complex .AND. matB%is_complex) THEN
       CALL ConvertMatrixToComplex(matA, converted_matrix)
       CALL PairwiseMultiplyMatrix(converted_matrix, matB, matC)
       CALL DestructMatrix(converted_matrix)
    ELSE IF (matA%is_complex .AND. matB%is_complex) THEN
#define LMAT local_data_c
#include "distributed_algebra_includes/PairwiseMultiply.f90"
#undef LMAT
    ELSE
#define LMAT local_data_r
#include "distributed_algebra_includes/PairwiseMultiply.f90"
#undef LMAT
    END IF
  END SUBROUTINE PairwiseMultiplyMatrix_ps
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  !> Compute the norm of a distributed sparse matrix along the rows.
  FUNCTION MatrixNorm_ps(this) RESULT(norm_value)
    !> The matrix to compute the norm of.
    TYPE(Matrix_ps), INTENT(IN) :: this
    !> The norm value of the full distributed sparse matrix.
    REAL(NTREAL) :: norm_value
    !! Local Data
    REAL(NTREAL), DIMENSION(:), ALLOCATABLE :: local_norm
    TYPE(Matrix_lsr) :: merged_local_data_r
    TYPE(Matrix_lsc) :: merged_local_data_c
    INTEGER :: ierr

    IF (this%is_complex) THEN
#define LMAT merged_local_data_c
#include "distributed_algebra_includes/MatrixNorm.f90"
#undef LMAT
    ELSE
#define LMAT merged_local_data_r
#include "distributed_algebra_includes/MatrixNorm.f90"
#undef LMAT
    END IF
  END FUNCTION MatrixNorm_ps
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  !> product = dot(Matrix A,Matrix B)
  !> Note that a dot product is the sum of elementwise multiplication, not
  !> traditional matrix multiplication.
  SUBROUTINE DotMatrix_psr(matA, matB, product)
    !> Matrix A.
    TYPE(Matrix_ps), INTENT(IN)  :: matA
    !> Matrix B.
    TYPE(Matrix_ps), INTENT(IN)  :: matB
    !> The dot product.
    REAL(NTREAL), INTENT(OUT) :: product

#include "distributed_algebra_includes/DotMatrix.f90"
  END SUBROUTINE DotMatrix_psr
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  !> product = dot(Matrix A,Matrix B)
  !> Note that a dot product is the sum of elementwise multiplication, not
  !> traditional matrix multiplication.
  SUBROUTINE DotMatrix_psc(matA, matB, product)
    !> Matrix A.
    TYPE(Matrix_ps), INTENT(IN)  :: matA
    !> Matrix B.
    TYPE(Matrix_ps), INTENT(IN)  :: matB
    !> The dot product.
    COMPLEX(NTCOMPLEX), INTENT(OUT) :: product

#include "distributed_algebra_includes/DotMatrix.f90"
  END SUBROUTINE DotMatrix_psc
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  !> Matrix B = alpha*Matrix A + Matrix B (AXPY)
  !> This will utilize the sparse vector increment routine.
  RECURSIVE SUBROUTINE IncrementMatrix_ps(matA, matB, alpha_in, threshold_in)
    !> Matrix A.
    TYPE(Matrix_ps), INTENT(IN)  :: matA
    !> Matrix B.
    TYPE(Matrix_ps), INTENT(INOUT)  :: matB
    !> Multiplier (default = 1.0).
    REAL(NTREAL), OPTIONAL, INTENT(IN) :: alpha_in
    !> For flushing values to zero (default = 0).
    REAL(NTREAL), OPTIONAL, INTENT(IN) :: threshold_in
    !! Local Data
    TYPE(Matrix_ps) :: converted_matrix
    REAL(NTREAL) :: alpha
    REAL(NTREAL) :: threshold
    INTEGER :: II, JJ

    !! Optional Parameters
    IF (.NOT. PRESENT(alpha_in)) THEN
       alpha = 1.0_NTREAL
    ELSE
       alpha = alpha_in
    END IF
    IF (.NOT. PRESENT(threshold_in)) THEN
       threshold = 0.0_NTREAL
    ELSE
       threshold = threshold_in
    END IF

    IF (matA%is_complex .AND. .NOT. matB%is_complex) THEN
       CALL ConvertMatrixToComplex(matB, converted_matrix)
       CALL IncrementMatrix(matA, converted_matrix, alpha, threshold)
       CALL CopyMatrix(converted_matrix, matB)
    ELSE IF (.NOT. matA%is_complex .AND. matB%is_complex) THEN
       CALL ConvertMatrixToComplex(matA, converted_matrix)
       CALL IncrementMatrix(converted_matrix, matB, alpha, threshold)
    ELSE IF (matA%is_complex .AND. matB%is_complex) THEN
#define LMAT local_data_c
#include "distributed_algebra_includes/IncrementMatrix.f90"
#undef LMAT
    ELSE
#define LMAT local_data_r
#include "distributed_algebra_includes/IncrementMatrix.f90"
#undef LMAT
    END IF

    CALL DestructMatrix(converted_matrix)

  END SUBROUTINE IncrementMatrix_ps
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  !> Will scale a distributed sparse matrix by a constant.
  SUBROUTINE ScaleMatrix_psr(this, constant)
    !> Matrix to scale.
    TYPE(Matrix_ps), INTENT(INOUT) :: this
    !> A constant scale factor.
    REAL(NTREAL), INTENT(IN) :: constant
    !! Local Data
    INTEGER :: II, JJ

    IF (this%is_complex) THEN
#define LOCALDATA local_data_c
#include "distributed_algebra_includes/ScaleMatrix.f90"
#undef LOCALDATA
    ELSE
#define LOCALDATA local_data_r
#include "distributed_algebra_includes/ScaleMatrix.f90"
#undef LOCALDATA
    END IF

  END SUBROUTINE ScaleMatrix_psr
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  !> Will scale a distributed sparse matrix by a constant.
  RECURSIVE SUBROUTINE ScaleMatrix_psc(this, constant)
    !> Matrix to scale.
    TYPE(Matrix_ps), INTENT(INOUT) :: this
    !> A constant scale factor.
    COMPLEX(NTCOMPLEX), INTENT(IN) :: constant
    !! Local Data
    TYPE(Matrix_ps) :: this_c
    INTEGER :: II, JJ

    IF (this%is_complex) THEN
#define LOCALDATA local_data_c
#include "distributed_algebra_includes/ScaleMatrix.f90"
#undef LOCALDATA
    ELSE
       CALL ConvertMatrixToComplex(this, this_c)
       CALL ScaleMatrix_psc(this_c, constant)
       CALL CopyMatrix(this_c, this)
       CALL DestructMatrix(this_c)
    END IF

  END SUBROUTINE ScaleMatrix_psc
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  !> Will scale a distributed sparse matrix by a constant.
  SUBROUTINE MatrixDiagonalScale_psr(this, tlist)
    !> Matrix to scale.
    TYPE(Matrix_ps), INTENT(INOUT) :: this
    !> A constant scale factor.
    TYPE(TripletList_r), INTENT(IN) :: tlist
    !! Local Data
    TYPE(Matrix_lsr) :: lmat
    TYPE(TripletList_r) :: filtered
    TYPE(Triplet_r) :: trip

#include "distributed_algebra_includes/ScaleDiagonal.f90"
  END SUBROUTINE MatrixDiagonalScale_psr
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  !> Will scale a distributed sparse matrix by a constant.
  RECURSIVE SUBROUTINE MatrixDiagonalScale_psc(this, tlist)
    !> Matrix to scale.
    TYPE(Matrix_ps), INTENT(INOUT) :: this
    !> A constant scale factor.
    TYPE(TripletList_c), INTENT(IN) :: tlist
    !! Local Data
    TYPE(Matrix_lsc) :: lmat
    TYPE(TripletList_c) :: filtered
    TYPE(Triplet_c) :: trip

#include "distributed_algebra_includes/ScaleDiagonal.f90"
  END SUBROUTINE MatrixDiagonalScale_psc
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  !> Compute the trace of the matrix.
  SUBROUTINE MatrixTrace_psr(this, trace_value)
    !> The matrix to compute the trace of.
    TYPE(Matrix_ps), INTENT(IN) :: this
    !> The trace value of the full distributed sparse matrix.
    REAL(NTREAL), INTENT(OUT) :: trace_value
    !! Local data
    TYPE(TripletList_r) :: triplet_list_r
    TYPE(TripletList_c) :: triplet_list_c
    !! Counters/Temporary
    INTEGER :: II
    TYPE(Matrix_lsr) :: merged_local_data_r
    TYPE(Matrix_lsc) :: merged_local_data_c
    INTEGER :: ierr

    IF (this%is_complex) THEN
#define TLIST triplet_list_c
#define LMAT merged_local_data_c
#define MPIDATATYPE MPINTCOMPLEX
#include "distributed_algebra_includes/MatrixTrace.f90"
#undef MPIDATATYPE
#undef LMAT
#undef TLIST
    ELSE
#define TLIST triplet_list_r
#define LMAT merged_local_data_r
#define MPIDATATYPE MPINTREAL
#include "distributed_algebra_includes/MatrixTrace.f90"
#undef MPIDATATYPE
#undef LMAT
#undef TLIST
    END IF
  END SUBROUTINE MatrixTrace_psr
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  !> Measure the asymmetry of a matrix NORM(A - A.T)
  FUNCTION MeasureAsymmetry(this) RESULT(norm_value)
    !> The matrix to measure
    TYPE(Matrix_ps), INTENT(IN) :: this
    !> The norm value of the full distributed sparse matrix.
    REAL(NTREAL) :: norm_value
    !! Local variables
    TYPE(Matrix_ps) :: tmat

    CALL TransposeMatrix(this, tmat)
    CALL ConjugateMatrix(tmat)
    CALL IncrementMatrix(this, tmat, alpha_in=-1.0_NTREAL)
    norm_value = MatrixNorm(tmat)
    CALL DestructMatrix(tmat)

  END FUNCTION MeasureAsymmetry
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  !> Make the matrix symmetric
  SUBROUTINE SymmetrizeMatrix(this)
    !> The matrix to symmetrize
    TYPE(Matrix_ps), INTENT(INOUT) :: this
    !! Local variables
    TYPE(Matrix_ps) :: tmat

    CALL TransposeMatrix(this, tmat)
    CALL ConjugateMatrix(tmat)
    CALL IncrementMatrix(tmat, this, alpha_in=1.0_NTREAL)
    CALL ScaleMatrix(this, 0.5_NTREAL)
    CALL DestructMatrix(tmat)

  END SUBROUTINE SymmetrizeMatrix
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  !> Transform a matrix B = P * A * P^-1
  !! This routine will check if P is the identity matrix, and if so
  !! just return A.
  SUBROUTINE SimilarityTransform(A, P, PInv, ResMat, pool_in, threshold_in)
    !> The matrix to transform
    TYPE(Matrix_ps), INTENT(IN) :: A
    !> The left matrix.
    TYPE(Matrix_ps), INTENT(IN) :: P
    !> The right matrix.
    TYPE(Matrix_ps), INTENT(IN) :: PInv
    !> The computed matrix P * A * P^-1
    TYPE(Matrix_ps), INTENT(INOUT) :: ResMat
    !> A matrix memory pool.
    TYPE(MatrixMemoryPool_p), INTENT(INOUT), OPTIONAL :: pool_in
    !> The threshold for removing small elements.
    REAL(NTREAL), INTENT(IN), OPTIONAL :: threshold_in
    !! Local variables
    TYPE(MatrixMemoryPool_p) :: pool
    TYPE(Matrix_ps) :: TempMat
    REAL(NTREAL) :: threshold

    !! Optional Parameters
    IF (.NOT. PRESENT(threshold_in)) THEN
       threshold = 0.0_NTREAL
    ELSE
       threshold = threshold_in
    END IF
    IF (.NOT. PRESENT(pool_in)) THEN
       CALL ConstructMatrixMemoryPool(pool, A)
    END IF

    !! Check if P is the identity matrix, if so we can exit early.
    IF (IsIdentity(P)) THEN
       CALL CopyMatrix(A, ResMat)
    ELSE
       !! Compute
       IF (PRESENT(pool_in)) THEN
          CALL MatrixMultiply(P, A, TempMat, &
               & threshold_in = threshold, memory_pool_in = pool_in)
          CALL MatrixMultiply(TempMat, PInv, ResMat, &
               & threshold_in = threshold, memory_pool_in = pool_in)
       ELSE
          CALL MatrixMultiply(P, A, TempMat, &
               & threshold_in = threshold, memory_pool_in = pool)
          CALL MatrixMultiply(TempMat, PInv, ResMat, &
               & threshold_in = threshold, memory_pool_in = pool)
       END IF
    END IF

    !! Cleanup
    IF (.NOT. PRESENT(pool_in)) THEN
       CALL DestructMatrixMemoryPool(pool)
    END IF
    CALL DestructMatrix(TempMat)
  END SUBROUTINE SimilarityTransform
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
END MODULE PSMatrixAlgebraModule
