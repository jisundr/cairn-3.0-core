// Conditional class-name joiner - no Tailwind conflict resolution needed
// here (this build has no utility-class collisions to merge), just a plain
// falsy-filter over literal class names from styles/design.css.
export function cn(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}
