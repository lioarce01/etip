import { apiClient } from "./client";
import type {
  Employee,
  EmployeeListResponse,
  EmployeeAvailability,
  CSVImportResult,
} from "@/types/api";

export async function listEmployees(params?: {
  page?: number;
  page_size?: number;
  search?: string;
  department?: string;
}): Promise<EmployeeListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.page_size) searchParams.set("page_size", String(params.page_size));
  if (params?.search) searchParams.set("search", params.search);
  if (params?.department) searchParams.set("department", params.department);
  return apiClient
    .get("api/v1/employees", { searchParams })
    .json<EmployeeListResponse>();
}

export async function getEmployee(id: string): Promise<Employee> {
  return apiClient.get(`api/v1/employees/${id}`).json<Employee>();
}

export async function getEmployeeAvailability(
  id: string,
  startDate: string,
  endDate: string
): Promise<EmployeeAvailability> {
  return apiClient
    .get(`api/v1/employees/${id}/availability`, {
      searchParams: { start_date: startDate, end_date: endDate },
    })
    .json<EmployeeAvailability>();
}

export async function importCSV(file: File): Promise<CSVImportResult> {
  const formData = new FormData();
  formData.append("file", file);
  return apiClient
    .post("api/v1/employees/import/csv", { body: formData })
    .json<CSVImportResult>();
}
