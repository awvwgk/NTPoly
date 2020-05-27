#include "SolverBase.h"
#include "PSMatrix.h"
#include "SolverParameters.h"

////////////////////////////////////////////////////////////////////////////////
namespace NTPoly {
////////////////////////////////////////////////////////////////////////////////
const int *SolverBase::GetIH(const Matrix_ps &dsm) { return dsm.ih_this; }

////////////////////////////////////////////////////////////////////////////////
int *SolverBase::GetIH(Matrix_ps &dsm) { return dsm.ih_this; }

////////////////////////////////////////////////////////////////////////////////
const int *SolverBase::GetIH(const SolverParameters &csp) {
  return csp.ih_this;
}

////////////////////////////////////////////////////////////////////////////////
int *SolverBase::GetIH(SolverParameters &csp) { return csp.ih_this; }
} // namespace NTPoly
