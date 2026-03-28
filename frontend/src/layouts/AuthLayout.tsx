import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";

export function AuthLayout() {
  const { user, isLoading } = useAuth();
  if (isLoading) return null; // Prevent flash of login page during session restore
  if (user) return <Navigate to="/dashboard" replace />;
  return <Outlet />;
}
