#ifndef DENSITYMATRIXSOLVERS_ch
#define DENSITYMATRIXSOLVERS_ch

void PM_wrp(const int *ih_Hamiltonian, const int *ih_InverseSquareRoot,
            const int *nel, int *ih_Density, const double *energy_value_out,
            const double *chemical_potential_out,
            const int *ih_solver_parameters);
void TRS2_wrp(const int *ih_Hamiltonian, const int *ih_InverseSquareRoot,
              const int *nel, int *ih_Density, const double *energy_value_out,
              const double *chemical_potential_out,
              const int *ih_solver_parameters);
void TRS4_wrp(const int *ih_Hamiltonian, const int *ih_InverseSquareRoot,
              const int *nel, int *ih_Density, const double *energy_value_out,
              const double *chemical_potential_out,
              const int *ih_solver_parameters);
void HPCP_wrp(const int *ih_Hamiltonian, const int *ih_InverseSquareRoot,
              const int *nel, int *ih_Density, const double *energy_value_out,
              const double *chemical_potential_out,
              const int *ih_solver_parameters);
// void HPCPPlus_wrp(const int *ih_Hamiltonian, const int *ih_InverseSquareRoot,
//                   const int *nel, int *ih_Density, const double
//                   *energy_value_out, const double *chemical_potential_out,
//                   const int *ih_solver_parameters);
#endif
