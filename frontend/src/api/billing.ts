import axiosInstance from './axiosInstance';

export interface CreditPack {
  price_id: string;
  credits: number;
  label: string;
}

export async function listCreditPacks(): Promise<{
  enabled: boolean;
  packs: CreditPack[];
}> {
  const { data } = await axiosInstance.get('/billing/credit-packs');
  return data;
}

export async function createCheckoutSession(priceId: string): Promise<{
  url: string;
  session_id: string;
}> {
  const { data } = await axiosInstance.post('/billing/checkout-session', {
    price_id: priceId,
  });
  return data;
}
