// Type declarations for template UI component packages
declare module "clsx" {
  export type ClassValue = any;
  export function clsx(...inputs: any[]): string;
  export default clsx;
}

declare module "tailwind-merge" {
  export function twMerge(...inputs: any[]): string;
}

declare module "@base-ui/react/*" {
  const content: any;
  export default content;
  export const Accordion: any;
  export const Dialog: any;
  export const Popover: any;
  export const Progress: any;
  export const Radio: any;
  export const RadioGroup: any;
  export const Slider: any;
  export const Switch: any;
}

declare module "lucide-react" {
  const content: any;
  export default content;
  export const ChevronDownIcon: any;
  export const ChevronRight: any;
  export const ChevronRightIcon: any;
  export const ChevronDown: any;
  export const ChevronUpIcon: any;
  export const CheckIcon: any;
  export const CircleIcon: any;
  export const XIcon: any;
  export const SearchIcon: any;
  export const Play: any;
  export const ArrowLeft: any;
  export const ArrowRight: any;
  export const PanelLeftIcon: any;
  export const MoreHorizontal: any;
  export const ChevronsUpDown: any;
  export const Plus: any;
  export const Check: any;
  export const X: any;
}

declare module "@tabler/icons-react" {
  const content: any;
  export default content;
  export const IconTrendingDown: any;
  export const IconTrendingUp: any;
  export const IconCamera: any;
  export const IconChartBar: any;
  export const IconDashboard: any;
  export const IconDatabase: any;
  export const IconFileAi: any;
  export const IconFileDescription: any;
  export const IconFileWord: any;
  export const IconFolder: any;
  export const IconHelp: any;
  export const IconInnerShadowTop: any;
  export const IconListDetails: any;
  export const IconReport: any;
  export const IconSearch: any;
  export const IconSettings: any;
  export const IconUsers: any;
  export const IconChevronDown: any;
  export const IconChevronLeft: any;
  export const IconChevronRight: any;
  export const IconChevronsLeft: any;
  export const IconChevronsRight: any;
  export const IconCircleCheckFilled: any;
  export const IconDotsVertical: any;
  export const IconGripVertical: any;
  export const IconLayoutColumns: any;
  export const IconLoader: any;
  export const IconPlus: any;
  export const IconCirclePlusFilled: any;
  export const IconMail: any;
}

declare module "recharts" {
  const content: any;
  export default content;
  export const Area: any;
  export const AreaChart: any;
  export const CartesianGrid: any;
  export const XAxis: any;
  export const ResponsiveContainer: any;
  export const Tooltip: any;
  export const Bar: any;
  export const BarChart: any;
  export const Line: any;
  export const LineChart: any;
}
