import React from 'react';
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar';
import {
  LayoutDashboard,
  AlertTriangle,
  Lightbulb,
  Users,
  Settings,
  Database,
} from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { useAnomalySummary } from '@/services/anomaly';

const navItems = [
  { title: 'Dashboard', url: '/dashboard', icon: LayoutDashboard },
  { title: 'Attribution', url: '/attribution', icon: Users },
  { title: 'Anomalies', url: '/anomalies', icon: AlertTriangle },
  { title: 'Recommendations', url: '/recommendations', icon: Lightbulb },
  { title: 'Settings', url: '/settings', icon: Settings },
];

// Admin-only items rendered inline after Dashboard
const adminNavItems = [
  { title: 'Ingestion', url: '/ingestion', icon: Database },
];

export function AppSidebar() {
  const { user } = useAuth();
  const anomalySummary = useAnomalySummary();
  const anomalyCount = anomalySummary.data?.active_count ?? 0;
  const anomalyBadgeColor =
    (anomalySummary.data?.critical_count ?? 0) > 0 ? 'bg-red-500' :
    (anomalySummary.data?.high_count ?? 0) > 0 ? 'bg-orange-400' :
    'bg-blue-500';

  return (
    <Sidebar>
      <SidebarHeader className="border-b px-4 py-3 h-14">
        <span className="text-lg font-bold tracking-tight">CloudCost</span>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item, index) => (
                <React.Fragment key={item.title}>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild>
                      <NavLink
                        to={item.url}
                        className={({ isActive }) =>
                          isActive ? 'bg-sidebar-accent text-sidebar-accent-foreground' : ''
                        }
                      >
                        <item.icon className="h-4 w-4" />
                        <span>{item.title}</span>
                        {item.title === 'Anomalies' && anomalyCount > 0 && (
                          <span className={`ml-auto flex h-5 min-w-5 items-center justify-center rounded-full px-1 text-[10px] font-semibold text-white ${anomalyBadgeColor}`}>
                            {anomalyCount > 99 ? '99+' : anomalyCount}
                          </span>
                        )}
                      </NavLink>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                  {index === 3 && user?.role === 'admin' &&
                    adminNavItems.map((adminItem) => (
                      <SidebarMenuItem key={adminItem.title}>
                        <SidebarMenuButton asChild>
                          <NavLink
                            to={adminItem.url}
                            className={({ isActive }) =>
                              isActive ? 'bg-sidebar-accent text-sidebar-accent-foreground' : ''
                            }
                          >
                            <adminItem.icon className="h-4 w-4" />
                            <span>{adminItem.title}</span>
                          </NavLink>
                        </SidebarMenuButton>
                      </SidebarMenuItem>
                    ))}
                </React.Fragment>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  );
}
