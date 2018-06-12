!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
!> Wraps the Hermite Solvers Module
MODULE HermiteSolversModule_wrp
  USE HermiteSolversModule, ONLY : HermitePolynomial_t, &
       & ConstructHermitePolynomial, DestructHermitePolynomial, &
       & SetHermiteCoefficient, HermiteCompute
  USE MatrixPSModule_wrp, ONLY : &
       & Matrix_ps_wrp
  USE DataTypesModule, ONLY : NTREAL
  USE FixedSolversModule_wrp, ONLY : FixedSolverParameters_wrp
  USE WrapperModule, ONLY : SIZE_wrp
  USE ISO_C_BINDING, ONLY : c_int
  IMPLICIT NONE
  PRIVATE
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  !> A wrapper for the polynomial data type.
  TYPE, PUBLIC :: HermitePolynomial_wrp
     TYPE(HermitePolynomial_t), POINTER :: DATA
  END TYPE HermitePolynomial_wrp
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  !! Hermite Polynomial type.
  PUBLIC :: ConstructHermitePolynomial_wrp
  PUBLIC :: DestructHermitePolynomial_wrp
  PUBLIC :: SetHermiteCoefficient_wrp
  !! Solvers.
  PUBLIC :: HermiteCompute_wrp
CONTAINS!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  !> Wrap the hermite polynomial constructor.
  PURE SUBROUTINE ConstructHermitePolynomial_wrp(ih_this, degree) &
       & bind(c,name="ConstructHermitePolynomial_wrp")
    INTEGER(kind=c_int), INTENT(INOUT) :: ih_this(SIZE_wrp)
    INTEGER(kind=c_int), INTENT(IN) :: degree
    TYPE(HermitePolynomial_wrp) :: h_this

    ALLOCATE(h_this%data)
    CALL ConstructHermitePolynomial(h_this%data,degree)
    ih_this = TRANSFER(h_this,ih_this)
  END SUBROUTINE ConstructHermitePolynomial_wrp
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  !> Destruct a polynomial object.
  PURE SUBROUTINE DestructHermitePolynomial_wrp(ih_this) &
       & bind(c,name="DestructHermitePolynomial_wrp")
    INTEGER(kind=c_int), INTENT(inout) :: ih_this(SIZE_wrp)
    TYPE(HermitePolynomial_wrp) :: h_this

    h_this = TRANSFER(ih_this,h_this)
    CALL DestructHermitePolynomial(h_this%data)
    DEALLOCATE(h_this%data)
  END SUBROUTINE DestructHermitePolynomial_wrp
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  !> Set coefficient of a polynomial.
  SUBROUTINE SetHermiteCoefficient_wrp(ih_this, degree, coefficient) &
       & bind(c,name="SetHermiteCoefficient_wrp")
    INTEGER(kind=c_int), INTENT(INOUT) :: ih_this(SIZE_wrp)
    INTEGER(kind=c_int), INTENT(IN) :: degree
    REAL(NTREAL), INTENT(IN) :: coefficient
    TYPE(HermitePolynomial_wrp) :: h_this

    h_this = TRANSFER(ih_this,h_this)
    CALL SetHermiteCoefficient(h_this%data, degree, coefficient)
  END SUBROUTINE SetHermiteCoefficient_wrp
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  !> Compute A Matrix Hermite Polynomial.
  SUBROUTINE HermiteCompute_wrp(ih_InputMat, ih_OutputMat, ih_polynomial, &
       & ih_solver_parameters) bind(c,name="HermiteCompute_wrp")
    INTEGER(kind=c_int), INTENT(IN)    :: ih_InputMat(SIZE_wrp)
    INTEGER(kind=c_int), INTENT(INOUT) :: ih_OutputMat(SIZE_wrp)
    INTEGER(kind=c_int), INTENT(IN)    :: ih_polynomial(SIZE_wrp)
    INTEGER(kind=c_int), INTENT(IN)    :: ih_solver_parameters(SIZE_wrp)
    TYPE(Matrix_ps_wrp) :: h_InputMat
    TYPE(Matrix_ps_wrp) :: h_OutputMat
    TYPE(HermitePolynomial_wrp)     :: h_polynomial
    TYPE(FixedSolverParameters_wrp)   :: h_solver_parameters

    h_InputMat = TRANSFER(ih_InputMat,h_InputMat)
    h_OutputMat = TRANSFER(ih_OutputMat, h_OutputMat)
    h_polynomial = TRANSFER(ih_polynomial, h_polynomial)
    h_solver_parameters = TRANSFER(ih_solver_parameters, h_solver_parameters)

    CALL HermiteCompute(h_InputMat%data, h_OutputMat%data, &
         & h_polynomial%data, h_solver_parameters%data)
  END SUBROUTINE HermiteCompute_wrp
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
END MODULE HermiteSolversModule_wrp
