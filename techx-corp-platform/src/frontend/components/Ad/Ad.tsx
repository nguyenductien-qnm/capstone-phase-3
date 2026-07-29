import { CypressFields } from '../../utils/enums/CypressFields';
import { useAd } from '../../providers/Ad.provider';
import { Card } from '@/components/ui/card';

const Ad = () => {
  const { adList } = useAd();
  const { text, redirectUrl } = adList[Math.floor(Math.random() * adList.length)] || { text: '', redirectUrl: '' };
  return <Card className="mx-auto my-4 max-w-7xl p-4 text-center" data-cy={CypressFields.Ad}><a href={redirectUrl} className="text-sm font-medium text-muted-foreground hover:text-foreground">{text}</a></Card>;
};

export default Ad;
