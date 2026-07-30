"use client"

import * as React from "react"
import {
  Sparkles,
  Telescope,
  ShoppingCart,
  Star,
  Settings2,
  Package,
} from "lucide-react"

import { NavMain } from "./nav-main"
import { NavProjects } from "./nav-projects"
import { NavUser } from "./nav-user"
import { TeamSwitcher } from "./team-switcher"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarRail,
} from "./ui/sidebar"

// Ecommerce Data
const data = {
  user: {
    name: "Astro Explorer",
    email: "user@techx.astro",
    avatar: "/images/avatars/user.jpg",
  },
  teams: [
    {
      name: "TechX Astro",
      logo: Telescope,
      plan: "Storefront",
    },
  ],
  navMain: [
    {
      title: "Shop",
      url: "/",
      icon: Package,
      isActive: true,
      items: [
        {
          title: "Hot Products",
          url: "/#hot-products",
        },
        {
          title: "Accessories",
          url: "/#accessories",
        },
      ],
    },
    {
      title: "Cart & Checkout",
      url: "/cart",
      icon: ShoppingCart,
      items: [
        {
          title: "View Cart",
          url: "/cart",
        },
      ],
    },
    {
      title: "AI Copilot",
      url: "/copilot",
      icon: Sparkles,
      items: [

        {
          title: "Shopping Copilot",
          url: "/copilot",
        },
        {
          title: "AI Evidence",
          url: "/dashboard",
        },
      ],
    },
    {
      title: "Account",
      url: "#",
      icon: Settings2,
      items: [
        {
          title: "Settings",
          url: "#",
        },
        {
          title: "Orders",
          url: "#",
        },
      ],
    },
  ],
  projects: [
    {
      name: "Featured: James Webb",
      url: "/product/2ZYFJ3GM2N",
      icon: Star,
    },
    {
      name: "Featured: Hubble",
      url: "/product/0PUK6V6EV0",
      icon: Star,
    },
  ],
}

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <TeamSwitcher teams={data.teams} />
      </SidebarHeader>
      <SidebarContent>
        <NavMain items={data.navMain} />
        <NavProjects projects={data.projects} />
      </SidebarContent>
      <SidebarFooter>
        <NavUser user={data.user} />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
