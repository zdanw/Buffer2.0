import axiosInstance from './axiosInstance';

export interface CreditGrant {
  id: string;
  user_id: string;
  source: string;
  quantity: number;
  remaining: number;
  status: string;
  note?: string | null;
  external_ref?: string | null;
  created_at?: string | null;
}

export interface CreditGrantList {
  remaining_total: number;
  grants: CreditGrant[];
}

export const listUserCreditGrants = async (userId: string): Promise<CreditGrantList> => {
  const response = await axiosInstance.get(`/auth/users/${userId}/credit-grants`);
  return response.data;
};

export const grantUserCredits = async (
  userId: string,
  quantity: number,
  note?: string
): Promise<CreditGrant> => {
  const response = await axiosInstance.post(`/auth/users/${userId}/credit-grants`, {
    quantity,
    note,
  });
  return response.data;
};
