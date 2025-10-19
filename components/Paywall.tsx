import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

interface PaywallProps {
  onUpgrade?(): void;
  href?: string;
  benefits?: string[];
  disabled?: boolean;
}

const defaultBenefits = ['Daily & weekly AI insights', 'Automated provider sync', 'Priority support'];

export function Paywall({ onUpgrade, href, benefits = defaultBenefits, disabled }: PaywallProps) {
  return (
    <Card className="border-dashed">
      <CardHeader>
        <CardTitle>Unlock Pro coaching</CardTitle>
        <CardDescription>Start your 14-day free trial to enable advanced insights and trends.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <ul className="space-y-2 text-sm">
          {benefits.map((benefit) => (
            <li key={benefit} className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-primary" />
              {benefit}
            </li>
          ))}
        </ul>
        {href ? (
          <Button asChild disabled={disabled}>
            <a href={href}>Upgrade now</a>
          </Button>
        ) : (
          <Button onClick={onUpgrade} disabled={disabled}>
            {disabled ? 'Processing…' : 'Upgrade now'}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
