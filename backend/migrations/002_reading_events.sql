-- 阅读事件与周汇总：在 001_initial.sql 基础上新增。
-- ORM create_all 建初表；本文件保留实际DDL，没有在线版本迁移执行器。
-- 既有库的 readers 新列由后端启动时幂等 ALTER 补齐（仅PostgreSQL）。

ALTER TABLE public.readers ADD COLUMN version integer NOT NULL DEFAULT 1;
ALTER TABLE public.readers ADD COLUMN source character varying(10) NOT NULL DEFAULT 'manual';
ALTER TABLE public.readers ADD COLUMN "week" character varying(10);

CREATE TABLE public.read_events (
    id integer NOT NULL,
    event_id character varying(80) NOT NULL,
    code character varying(60) NOT NULL,
    article character varying(120) NOT NULL,
    start character varying(40) NOT NULL,
    "end" character varying(40) NOT NULL,
    ratio double precision NOT NULL,
    state character varying(20) NOT NULL DEFAULT 'active',
    revoke_reason text,
    created character varying(40)
);
CREATE SEQUENCE public.read_events_id_seq AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;
ALTER SEQUENCE public.read_events_id_seq OWNED BY public.read_events.id;
ALTER TABLE ONLY public.read_events ALTER COLUMN id SET DEFAULT nextval('public.read_events_id_seq'::regclass);
ALTER TABLE ONLY public.read_events ADD CONSTRAINT read_events_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.read_events ADD CONSTRAINT read_events_event_id_key UNIQUE (event_id);

CREATE TABLE public.revocations (
    id integer NOT NULL,
    event_id character varying(80) NOT NULL,
    reason text,
    created character varying(40)
);
CREATE SEQUENCE public.revocations_id_seq AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;
ALTER SEQUENCE public.revocations_id_seq OWNED BY public.revocations.id;
ALTER TABLE ONLY public.revocations ALTER COLUMN id SET DEFAULT nextval('public.revocations_id_seq'::regclass);
ALTER TABLE ONLY public.revocations ADD CONSTRAINT revocations_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.revocations ADD CONSTRAINT revocations_event_id_key UNIQUE (event_id);

CREATE TABLE public.weekly_summaries (
    id integer NOT NULL,
    code character varying(60) NOT NULL,
    "week" character varying(10) NOT NULL,
    state character varying(20) NOT NULL DEFAULT 'pending',
    weekly_reading double precision,
    completion double precision,
    night_share double precision,
    detail json,
    base_reader_version integer,
    updated character varying(40)
);
CREATE SEQUENCE public.weekly_summaries_id_seq AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;
ALTER SEQUENCE public.weekly_summaries_id_seq OWNED BY public.weekly_summaries.id;
ALTER TABLE ONLY public.weekly_summaries ALTER COLUMN id SET DEFAULT nextval('public.weekly_summaries_id_seq'::regclass);
ALTER TABLE ONLY public.weekly_summaries ADD CONSTRAINT weekly_summaries_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.weekly_summaries ADD CONSTRAINT uq_summary_code_week UNIQUE (code, "week");
