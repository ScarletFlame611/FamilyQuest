import type { components } from "./schema";

type Schemas = components["schemas"];

export type Tokens = Schemas["TokenOut"];
export type Me = Schemas["MeOut"];
export type Family = Schemas["FamilyOut"];
export type Member = Schemas["MemberOut"];
export type Task = Schemas["TaskOut"];
export type TaskCreate = Schemas["TaskCreateIn"];
export type TaskIcon = Schemas["TaskIcon"];
export type Balance = Schemas["BalanceOut"];
export type Entry = Schemas["EntryOut"];
export type RewardOffer = Schemas["RewardOfferOut"];
export type RewardIcon = Schemas["RewardIcon"];
export type Purchase = Schemas["PurchaseOut"];
export type Goal = Schemas["GoalOut"];
export type GoalIcon = Schemas["GoalIcon"];
export type ChildEventType = Schemas["ChildEventType"];
export type ChildSession = Schemas["ChildSessionOut"];
export type SessionEvents = Schemas["SessionEventsOut"];
