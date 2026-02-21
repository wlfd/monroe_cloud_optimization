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

const navItems = [
  { title: 'Dashboard', url: '/dashboard', icon: LayoutDashboard },
  { title: 'Anomalies', url: '/anomalies', icon: AlertTriangle },
  { title: 'Recommendations', url: '/recommendations', icon: Lightbulb },
  { title: 'Attribution', url: '/attribution', icon: Users },
  { title: 'Settings', url: '/settings', icon: Settings },
];

const adminNavItems = [
  { title: 'Ingestion', url: '/ingestion', icon: Database },
];

export function AppSidebar() {
  const { user } = useAuth();

  return (
    <Sidebar>
      <SidebarHeader className="border-b px-4 py-3">
        <span className="text-lg font-bold tracking-tight">CloudCost</span>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild>
                    <NavLink
                      to={item.url}
                      className={({ isActive }) =>
                        isActive ? 'bg-sidebar-accent text-sidebar-accent-foreground' : ''
                      }
                    >
                      <item.icon className="h-4 w-4" />
                      <span>{item.title}</span>
                    </NavLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
              {user?.role === 'admin' &&
                adminNavItems.map((item) => (
                  <SidebarMenuItem key={item.title}>
                    <SidebarMenuButton asChild>
                      <NavLink
                        to={item.url}
                        className={({ isActive }) =>
                          isActive ? 'bg-sidebar-accent text-sidebar-accent-foreground' : ''
                        }
                      >
                        <item.icon className="h-4 w-4" />
                        <span>{item.title}</span>
                      </NavLink>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  );
}
