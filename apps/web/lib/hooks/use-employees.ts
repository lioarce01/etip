"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listEmployees,
  listDepartments,
  getEmployee,
  getEmployeeAvailability,
  importCSV,
} from "@/lib/api/employees";

export const employeeKeys = {
  all: ["employees"] as const,
  list: (params?: object) => ["employees", "list", params] as const,
  departments: ["employees", "departments"] as const,
  detail: (id: string) => ["employees", "detail", id] as const,
  availability: (id: string, start: string, end: string) =>
    ["employees", "availability", id, start, end] as const,
};

export function useEmployees(params?: Parameters<typeof listEmployees>[0]) {
  return useQuery({
    queryKey: employeeKeys.list(params),
    queryFn: () => listEmployees(params),
  });
}

export function useDepartments() {
  return useQuery({
    queryKey: employeeKeys.departments,
    queryFn: listDepartments,
  });
}

export function useEmployee(id: string) {
  return useQuery({
    queryKey: employeeKeys.detail(id),
    queryFn: () => getEmployee(id),
    enabled: !!id,
  });
}

export function useEmployeeAvailability(
  id: string,
  startDate: string,
  endDate: string
) {
  return useQuery({
    queryKey: employeeKeys.availability(id, startDate, endDate),
    queryFn: () => getEmployeeAvailability(id, startDate, endDate),
    enabled: !!id && !!startDate && !!endDate,
  });
}

export function useImportCSV() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: importCSV,
    onSuccess: () => qc.invalidateQueries({ queryKey: employeeKeys.all }),
  });
}
