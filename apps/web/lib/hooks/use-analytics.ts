import { useQuery } from "@tanstack/react-query";
import { getAnalytics } from "@/lib/api/analytics";

export function useAnalytics() {
  return useQuery({ queryKey: ["analytics"], queryFn: getAnalytics });
}
