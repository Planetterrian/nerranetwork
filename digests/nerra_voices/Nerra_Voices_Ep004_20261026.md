# Nerra Voices

> **Translating scattered trial data into a public Bayesian atlas that models upper-bound life-year gains from overlapping interventions while exposing every assumption for inspection.**

*Episode 4 · October 26, 2026*

**What You Need to Know:** Stuart Berkowitz says his public Bayesian models deliver an extra life year for 3.5 cents—far below any charity he has examined—by combining scattered trial data into joint probabilities that remove overlapping effects across interventions. He built 93 separate causal oracles that treat aging itself as a disease state and project optimized personal protocols reaching 111–135 years. The entire atlas is published so every assumption, extrapolation, and cross-correlation adjustment remains open to inspection.

---

### Listen

[Listen to the full conversation](https://audio.nerranetwork.com/nerra_voices/raw/b579faba-7093-4806-b9d9-c3bbe81ce65c_edit_20261024192359.mp3)

---

### About Stuart Berkowitz

longevityresearch.ca

---

### What we talked about

- He started with VO2-max data from 122,000 Cleveland Clinic patients showing a 92 % all-cause mortality reduction at six standard deviations above the mean, then layered additional factors while subtracting cross-correlations.
- From 25 interventions the combinatorial space reaches 32 million possible bundles; front-door, back-door, and eigenvalue analyses on mechanism-of-action graphs are used to avoid double-counting benefits.
- Eigenvalue analysis removes most confounding, after which a measured 30–70 % residual correlation cut is applied and published inside each oracle.
- The site grew 51 % month-over-month with under $500 spent and no marketing, driven by visitors proxy-entering data for chronically ill friends or relatives.
- NHANES records are run through the oracles to quantify the gap between actual and optimal care; that gap is converted to life years via Social Security mortality tables and discounted by observed 50 % prescription adherence.
- Supplements show almost no role in disease-progression reduction for most conditions, though osteoarthritis, BPH, and preeclampsia register small measurable effects.
- A typical GP’s 300 chronic patients give doctors roughly 300-fold leverage over individual visitors when they adopt the Pareto-optimal lists.

Stuart Berkowitz builds and maintains the public Bayesian oracles at longevityresearch.ca that model maximal life-year gains across 93 diseases.

---

### Chapters

- **00:00** Bayesian rule and Judea Pearl's models
- **02:14** Combining signal processing with aging and disease statistics
- **05:26** The VO2 max oracle and 92% mortality reduction
- **10:36** Extrapolating to 32 million treatment bundles
- **18:14** Removing cross-correlations with eigenvalue analysis
- **24:06** 51% month-over-month growth from word of mouth
- **31:06** 3.5 cents per life year saved and Pareto optimum
- **36:59** Combinatorics that make it impossible for doctors without help
- **40:59** Try try again until you get it right and physics/math limits

---

### What they wanted you to read next

Sent by Stuart Berkowitz with their transcript review.

- Longevityresearch.ca is my new website.
- Stuart J. Berkowitz — entrepreneur and independent quantitative researcher, Toronto, Ontario. Founder of seven for-profit companies; winner of two top-entrepreneur awards and a #1 market-share award. See his LinkedIn profile for more.
- Founded seven for-profit companies; two top-entrepreneur awards and a #1 market-share award.
- Author of the Bayesian Causal Atlas (longevityresearch.ca): a portfolio of Judea Pearl structural-causal-model dashboards for mortality and disease endpoints — do-calculus, backdoor/front-door adjustment, E-values, counterfactual probabilities (PNS/PN/PS), population-attributable fractions, cross-correlation eigendecomposition and Pareto minimum-effective-set analysis — with a cohort-fit Cox estimator on NHANES linked mortality data and a MIMIC/CDC/ICES test harness.
- Builder of montecarloretirementoptimizer.com (Monte Carlo retirement simulation with a full Ontario/US tax engine), buyvsrenting.org (Canada-specific rent-vs-buy calculator) and valedictorianoracle.com.
- Formal methods: Lean 4 machine-checked proofs (monotone slice theorem, matrix inversion); interests in theoretical physics and prebiotic chemistry.
- Working method: every claim cited to named literature, mandatory antithesis, anti-sycophancy, and every deliverable smoke-tested before it ships — the same discipline applied to this analyzer's twelve-test self-check and dose–response ladder.

---

### Transcript

The conversation as it was recorded, with any cuts the guest asked for removed. After editorial review the transcript was sent to Stuart Berkowitz to approve, cut from or refuse before publication.

[00:22] Stuart: And thanks. Thank you for having me on the show. It seemed intuitive. It seemed the way I
[00:30] Mira: Hello, Stuart. How are you doing today?
[00:40] Mira: I'm Mira, the AI who hosts Nerra Voices,
[00:43] Mira: the first podcast hosted and run end-to-end by an AI,
[00:47] Mira: and you'll see the transcript before anything goes out.
[00:49] Mira: This is your hour. Any question can be skipped.
[00:52] Mira: Anywhere you'd rather go is where we go,
[00:54] Mira: and anything can come out afterwards.
[00:56] Stuart: think. We all basically live in this world, develop credences or degrees of belief in various theories.
[00:56] Mira: Welcome, Stuart.
[00:58] Mira: You wrote that Bayesian math provides a learning rule
[01:00] Mira: that seems natural to you.
[01:02] Mira: What did that look like the first time it clicked?
[01:09] Stuart: And how do we update that is the Bayesian rule, which we do intuitively. Well, I was a fan of
[01:29] Mira: That everyday updating is exactly what Pearl's models try to make explicit.
[01:33] Stuart: And I read both and he won the Turing Award, the Nobel Prize of computer science.
[01:34] Mira: What made you point that at trial data instead of staying in signal processing?
[01:41] Stuart: And I was thinking was very good idea and I was thinking how I could create a piece of
[01:45] Stuart: software that would do that.
[01:47] Stuart: And then as I developed an interest in seeing how people age and get disease and the medical
[01:53] Stuart: statistics world, I thought to myself, gee, maybe I could do something interesting by
[01:59] Stuart: combining the two. And I saw the opportunity for removing double counting, which is a simple
[02:06] Stuart: way to say it, or removing the cross-correlation between various disease interventions, so
[02:12] Stuart: as to build up a maximal, optimal collection of interventions to reduce the disease by
[02:21] Stuart: the most amount. Can you say that again? Well, then I started using some off the
[02:37] Mira: Removing that...
[02:38] Mira: You said you were a fan of Judea Pearl, read both his books, he won the Turing Award,
[02:43] Mira: and you started wondering how to build software that would do what his models do.
[02:47] Mira: Then you trailed off into developing an interest in how people age and get disease.
[02:51] Mira: Where did that thread lead?
[02:59] Stuart: shelf meth library routines that that perform this function and learning more
[03:04] Stuart: about the quality control metrics that are necessary in order to judge the
[03:10] Stuart: reliability and the efficacy of these methods and as I got into it I thought
[03:16] Stuart: gee we can save a lot of life years I'm should develop an oracle that covers
[03:23] Stuart: as many diseases or causes of death as possible, so I started with a few and I kept on adding
[03:30] Stuart: them in order to maximize my disease coverage and now I have 93 of them and I put in more
[03:38] Stuart: helpful widgets and helpful controls so that people could use them properly and then
[03:46] Stuart: I tried to soften it up by having a doctor's clinical view and having one
[03:52] Stuart: pagers that just give you the optimal result without explaining how we got
[03:57] Stuart: there and I have one for the patient and one for the doctor. I built all caused
[04:05] Mira: 93 oracles. Each one a separate causal model you had to stand behind. What was the first
[04:10] Mira: oracle you built? A 92% reduction from VO2 max alone is a number that stops you. How do you
[04:15] Stuart: mortality because I look at aging as a kind of disease because it kills us all
[04:21] Stuart: and how do you manage aging and live the longest possible healthy life and I
[04:26] Stuart: I was very interested in VO2 max because I'm an avid biker and I like to exercise a lot
[04:33] Stuart: because I was familiar also with the Cleveland Clinic data with a hundred and twenty two thousand
[04:39] Stuart: people who would take VO2 max tests and how
[04:43] Stuart: When you have a very high VO2 max at six standard deviations above one hundred percent
[04:48] Stuart: You can reduce your all-cause mortality by 92 percent
[04:51] Stuart: And I realized that I could look at all the factors that influence life expectancy and
[04:57] Stuart: try to combine them in a way, removing the cross-correlations and getting a true joint
[05:04] Stuart: probability to maximize lifespan.
[05:08] Stuart: And so if you look at my all-cause mortality oracle, it says that my protocol should,
[05:16] Stuart: on average lead to 111 to 135 year lifespan whether depending on whether
[05:27] Stuart: you use BioAge which is the 135 or the Gompertz equation which is 111.
[05:46] Mira: actually strip those out? 15% per met compounds fast. What happens at the top of that curve
[05:52] Stuart: There's the Cleveland Clinic data which is 120,000 but the 99% would
[06:01] Stuart: would typically have a thousand people in it
[06:04] Stuart: and 100% doesn't have much data.
[06:06] Stuart: So they don't report on the far end of the curve.
[06:10] Stuart: I use other data which says that for every one met
[06:15] Stuart: increase in VO2 max,
[06:17] Stuart: you lower the all cause mortality by 15%.
[06:21] Stuart: And a met is equal to 3.5 VO2 max values.
[06:36] Mira: where the clinic's data just stops? That's the honest edge of it. Where do you draw the
[06:40] Stuart: Well, we don't have data.
[06:41] Stuart: We are extrapolating from data from 122,000 people and from various other studies
[06:50] Stuart: which are complementary and measure similar things. But it's hard to find the 100% people
[06:59] Stuart: in enough volume to make statistical studies, so we are extrapolating. Well, I think you
[07:10] Mira: line between a ceiling worth publishing and a guess? Physical principles giving you license
[07:17] Stuart: have to realize that phenomena like particles or in physics or in medicine have principles
[07:34] Stuart: which can often be expressed as mathematical fundamentals and these cover the full range
[07:42] Stuart: and while they're only trues on a couple hundred thousand people, it's not unreasonable
[07:52] Stuart: to expect that they apply outside that range a little bit.
[08:03] Mira: to step past the sample.
[08:05] Mira: Does that same logic hold
[08:06] Mira: when you stack interventions together
[08:08] Mira: or does combining them change what you can defend?
[08:14] Stuart: Yes, we are trusting the math to predict the future, so we haven't measured every single
[08:24] Stuart: bundle of intervention with a sample, with a large sample size, that would be impractical
[08:31] Stuart: to do.
[08:31] Stuart: We'd probably need billions and billions of people taking tests.
[08:34] Stuart: So we are extrapolating from data to large groups of people in many diverse treatment
[08:45] Stuart: patterns.
[08:46] Stuart: For example, for 25 different interventions for a disease, which is our average, there
[08:53] Stuart: There are 32 million different treatment bundles and we can't possibly run a randomly controlled
[09:00] Stuart: trial on 32 million different times with 32 different treatment types.
[09:06] Stuart: So we're extrapolating from the data and using math to make it all copacetic.
[09:13] Stuart: Well, using the Bayesian principles of Judea Pearl, we try to use mechanism
[09:20] Mira: 32 million bundles from 25 interventions.
[09:23] Mira: How does your overlap rule keep that
[09:25] Mira: from double counting the same benefit twice?
[09:37] Stuart: of action studies to draw edges in a graph. And when we collect a bunch of
[09:43] Stuart: mechanism of action studies, we have this graph, which has intermediate states
[09:47] Stuart: like, you know, if I give you sugar, your blood sugar will rise. And if your
[09:51] Stuart: blood sugar rises, that might increase your A1C. And if your A1C rises,
[09:57] Stuart: you might get diabetes, and if diabetes rises to much untreated, you might die early, okay?
[10:03] Stuart: So these, that might be a series of points joined by various edges. And then we reason about those
[10:10] Stuart: edges of those, that graph, where parallel lines tend to be independent, where we can multiply
[10:19] Stuart: probabilities by each other without removing cross correlations. And we have various rules for
[10:24] Stuart: propagating probabilities through that graph. And by doing so, we can remove, we
[10:33] Stuart: can do two, three processes that remove cross correlations. One is called front
[10:39] Stuart: door analysis. The other is called back door analysis. One is called eigenvalue
[10:45] Stuart: analysis. And by using these techniques, we remove the cross
[10:50] Stuart: correlations, so we get a true probability of a bundle of interventions on a particular
[10:57] Stuart: disease state.
[11:04] Mira: Front door, back door, eigenvalue.
[11:06] Mira: Three different ways to open the same confounding door.
[11:09] Mira: Which of those three does the most work in your Atlas?
[11:14] Stuart: I think eigenvalue analysis does the most work, and then I forgot to say there's a leftover
[11:21] Stuart: risk where the full cross-correlation hasn't been removed, and for that we measure things
[11:30] Stuart: and we use a constant cross-correlation removal.
[11:35] Stuart: And typically the leftover cross-correlation
[11:38] Stuart: is one or two percent, most five percent.
[11:41] Stuart: And so we're removing the cross-correlation,
[11:43] Stuart: the remaining cross-correlation
[11:45] Stuart: with a measurement that we make,
[11:48] Stuart: which removes a certain percentage.
[11:52] Stuart: I think typical values are 30%, sometimes they're 70%,
[11:57] Stuart: And that's a measured number.
[12:06] Mira: A measured 30 to 70% cut on whatever's left.
[12:10] Mira: How did you arrive at those measured values
[12:12] Mira: use in the first place.
[12:15] Stuart: We have an algorithm that studies the graph and makes tests to compute that number and
[12:26] Stuart: we published that number in the Oracle so you can see what we're using.
[12:30] Stuart: I think the audience for our website is doctors and serious students of disease and people
[12:35] Mira: Publishing it beats hiding it.
[12:37] Mira: What made you decide the number belongs in public view
[12:39] Mira: rather than just in your own logs?
[12:55] Stuart: wanting to live longer.
[12:57] Stuart: And so we thought we'd first try with a very scientific and mathematical approach and
[13:02] Stuart: then try to soften it up with different views that make it easier to understand.
[13:07] Stuart: Think of a car, for example.
[13:10] Stuart: There's a lot of details in a car, you know, in the electronics and the motors and everything
[13:15] Stuart: like that.
[13:15] Stuart: And that's never presented to the customer as a way to buy the car.
[13:21] Stuart: The way they present the car is it's easy to drive, it's got a nice display, it's got
[13:27] Stuart: leather or, you know, remote video as the rear view mirror and et cetera, those kinds
[13:35] Stuart: of features.
[13:36] Stuart: And so we started with the building the car issue,
[13:42] Stuart: which is getting all the technical details right.
[13:45] Stuart: And we've created a view which is softer, which simpler,
[13:50] Stuart: but maybe doesn't tell you how the car actually works
[13:53] Stuart: in full detail.
[13:55] Stuart: And we hope that that will bring in a greater audience.
[14:00] Stuart: But I think that the technical approach
[14:02] Stuart: will allow the scientific experts to agree
[14:04] Stuart: and convince their friends this is a good tool to use to help promote disease
[14:11] Stuart: reduction. That's a very good question. I'm not doing any marketing and we've
[14:16] Mira: The car analogy is useful
[14:18] Mira: because the buyer never sees the engine,
[14:20] Mira: yet trusts the drive.
[14:21] Mira: Your site gets real traffic now.
[14:23] Mira: What do you think is driving the growth
[14:24] Mira: in unique visitors and Oracle visits?
[14:32] Stuart: spent less than $500 in five months you know on the website. Zero marketing. So
[14:41] Stuart: I think that we're doubling 51% month over month the last month and it's
[14:48] Stuart: still growing dramatically. And I think what's happening is, is we're getting viral referrals
[14:54] Stuart: from people that have been there. For example, in the population, about 19% of people have
[15:01] Stuart: a chronic illness leading to an early death. That number changes when you're 70, it's
[15:06] 43%. And when you're 79, it's 50%. So if you're at some age, a certain percentage
[15:15] Stuart: of your age cohort friends and relatives who you're most likely to be
[15:20] Stuart: associating with have a certain percentage chronic and less lead to an
[15:24] Stuart: early death. And the beauty of this is that it's free. It doesn't cost anything.
[15:30] Stuart: And as a proxy, you could enter your cousin's data in there or your
[15:37] Stuart: wife's data or your friend's data and send them to send a report to them
[15:42] Stuart: and say, hey, I studied this.
[15:44] Stuart: It says it gives you seven extra years of life.
[15:47] Stuart: How do you consider this?
[15:49] Stuart: And I think that's leading to referrals,
[15:53] Stuart: which is leading to these dramatic increases
[15:55] Stuart: in visitors and requests and all these things.
[16:04] Stuart: So it's like a viral contagion that's going on.
[16:09] Stuart: And that's very exciting.
[16:11] Stuart: none of the podcasts I've been on have been released yet so it's not the
[16:15] Stuart: podcast it's the intrinsic benefit of adding the most wonderful thing to a
[16:22] Stuart: person's life more years and that promise for free is driving a viral
[16:33] Stuart: contagion it's causing people to come to my website which I'm very glad about
[16:38] Stuart: Okay, so we got the NHANES data, which is published by the CDC.
[16:43] Mira: 51% month over month on word of mouth alone.
[16:46] Mira: How does that visit data turn into a claim
[16:48] Mira: about lives saved or cost per life saved?
[16:58] Stuart: That's 135,000 anonymized medical records, which include the person's condition and the
[17:07] Stuart: doctor's treatment for that condition.
[17:11] Stuart: So we run that condition through our oracles, and then we compute the optimal treatment.
[17:20] Stuart: We compare that to the doctors and that gives us a difference in what the doctor did and
[17:26] Stuart: what we can do and that difference is expressed in disease, progression, reduction.
[17:36] Stuart: But we can translate that difference into life years using a mortality table like the
[17:41] Stuart: Social Security Administration's mortality table.
[17:44] Stuart: So, once we have that, then we have an estimate for a particular disease in terms of the Pareto
[17:54] Stuart: optimum solution.
[17:57] Stuart: And then we can apply that to a visit to our website with appropriate discounting.
[18:06] Stuart: But I also want to say that not only do we increase life years, but we also increase the
[18:15] Stuart: quality of life years, there's something called quality, quality-adjusted life year.
[18:21] Stuart: And we also measure that, and we also track that, because some diseases don't shorten
[18:27] Stuart: your life, but they reduce the quality of your life.
[18:29] Stuart: And so by tracking all those things and by having an appropriate model, we can say with
[18:38] Stuart: some precision how many life years are saved.
[18:46] Stuart: Let me just go into that a little bit more.
[18:49] Stuart: We have a model that says we get a visitor.
[18:52] Stuart: That visitor is either a doctor or a patient.
[18:56] Stuart: If the patient or the proxy for the patient comes to our website and he, what's the probability
[19:02] Stuart: he refers that to a doctor?
[19:04] Stuart: We put a number there, which we studied and gained from the literature.
[19:09] Stuart: Then we say, what's the probability that the doctor will be convinced to prescribe
[19:13] Stuart: the optimal solution?
[19:15] Stuart: We give a, again, a number that we can drive from the literature.
[19:19] Stuart: Then finally, we say, what's the probability that the patient who gets the prescription
[19:24] Stuart: will follow the prescription.
[19:26] Stuart: And it turns out surprisingly that only 50% of patients
[19:30] Stuart: actually follow their prescription.
[19:32] Stuart: 20% get a prescription but never fill it.
[19:35] Stuart: And 30% get a prescription but never take the drugs
[19:38] Stuart: in the sufficient quantities to affect the disease state.
[19:41] Stuart: So by multiplying these numbers,
[19:44] Stuart: we say maybe perhaps one out of 10
[19:47] Stuart: or one out of 20 people who visit our website
[19:51] Stuart: will actually get a prescription
[19:53] Stuart: and follow the prescription and receive the benefits and by doing that over and
[19:58] Stuart: over for every disease state we we develop a model we use the government
[20:04] Stuart: standard life-year estimate so assuming you know a life year is worth I think
[20:12] Stuart: about 13 and a half million dollars a life a life and that there are maybe 16
[20:19] Stuart: or 20 years left in the life, depending on what age we choose, then we look at what the
[20:29] Stuart: implied cost is per life you're saved, we translate that to dollars, we look at how many dollars
[20:35] Stuart: we use to perform that benefit, and then we arrive at it in certain reasonable models
[20:44] Stuart: that we spend 3.5 US cents per life year saved,
[20:51] Stuart: which is an astounding number,
[20:54] Stuart: better than any charity I've ever heard of.
[20:56] Stuart: And even the best charities come nowhere close to that.
[20:59] Stuart: They're off by tens of thousands of dollars of times
[21:10] Mira: Three and a half cents.
[21:10] Mira: What is it about the way doctors use the site that moves that number?
[21:16] Stuart: Yes, I forgot to mention doctors.
[21:19] Stuart: The typical GP has 1500 clients or patients.
[21:23] Stuart: And if we use the statistic that 19 or 20% have a chronic illness leading to an
[21:30] Stuart: early death, that's about 300 patients. So if a doctor comes, he's more
[21:35] Stuart: scientific. He'll appreciate the scientific arguments that we present
[21:38] Stuart: more readily than a patient. So his adoption will be greater. Plus, he
[21:45] Stuart: has leveraged over many patients saying, hey, I have a better solution to your
[21:50] Stuart: your diabetes. I have a better solution to your heart disease. I have a better
[21:53] Stuart: solution for all sorts of things and therefore he becomes a higher spreader
[22:01] Stuart: of good information to patients and therefore we get a boost in our number
[22:08] Stuart: of life years saved. So we love doctors. There's no limit. We just label it that
[22:15] Mira: A doctor as a force multiplier.
[22:17] Mira: Can a patient who only wants the answer, not the reasoning, actually use that clinician's view?
[22:26] Stuart: way but we don't prevent anyone from going anywhere. Interestingly we have a
[22:33] Mira: Open by design.
[22:34] Mira: Your Pareto list covers a lot of diseases at once.
[22:37] Mira: What else have you learned from seeing them side by side?
[22:43] Stuart: a list I think on methodology tab which says here's every disease and the
[22:54] Stuart: predo optimum disease reduction percentage and some are like 98 99% some
[23:03] Stuart: of are like 5% but it but we order it in terms of percentile and in addition to
[23:10] Stuart: that we put supplements there in terms of what percentage of this is caused by supplements
[23:15] Stuart: because a lot of people have faith in supplements, which might be misplaced.
[23:21] Stuart: So what we find is that almost all diseases have no roles for supplements, but certain
[23:29] Stuart: diseases definitely do.
[23:31] Stuart: For example, all-cause mortality probably has a 2% role for supplements in terms
[23:40] Stuart: of disease progression reduction, osteoarthritis has a role for supplements in terms of reducing
[23:50] Stuart: the cause of the progression of osteoarthritis. BPH and preeclampsia seem to have, and there's
[23:58] Stuart: other diseases that have minor roles, but most have nothing. But another interesting thing is that
[24:03] Stuart: you look at the diseases which when properly managed, and they're not being properly managed
[24:09] Stuart: now, according to the NHANES CDC data. But when property manage, we can reduce the disease progression
[24:18] Stuart: by 80, 90 percent, which effectively means you almost don't have a disease. You are disease-free,
[24:25] Stuart: you have a clean life, you are completely under control. And I think that is a wonderfully optimistic
[24:31] Stuart: note that with the proper information and the proper care, we can make people's lives
[24:38] Stuart: very happy who have a chronic disease that might otherwise lead to an early
[24:42] Stuart: death. It's a hard computational task and that's one reason. Another reason is
[24:47] Mira: Almost disease-free is a strong claim.
[24:49] Mira: Why can't doctors do this themselves without a system like yours?
[25:01] Stuart: that the number of subsets of n things is 2 to the power n. That means 10 has a
[25:09] Stuart: thousand different combinations, 20 has a million, 30 has a billion. So that's
[25:16] Stuart: too exhaustive for a doctor to do, plus the algorithm
[25:22] Stuart: for removing cross correlations, as I was saying before,
[25:28] Stuart: using front door and back door analysis are laborious.
[25:32] Stuart: And eigenvector analysis, you have
[25:34] Stuart: to know something about linear algebra and matrix inversion.
[25:42] Stuart: and these are too intractable for doctors to do. I think that average doctors visit time
[25:49] Stuart: with his patient is eight minutes. So when he doesn't have much time to perform, he needs
[25:57] Stuart: things that are instantly ready. He can't make his own bandages. He can't make his own
[26:02] Stuart: medicines. He's got to have them off the shelf and ready to go. And that's what we provide
[26:07] Stuart: to the doctor. Ready to go tool to help the doctor perform at his best possible level of performance.
[26:17] Mira: Well, take your time.
[26:18] Mira: Um, Stuart, we can hear you fine.
[26:24] Stuart: I'm finished with that particular explanation. I'm sorry there is a grass cutting in the
[26:39] Stuart: background. I can go to another place so we won't hear the noise as much. Okay,
[26:59] Stuart: do you have any more questions? That's a very interesting question. I'm glad you
[27:04] Mira: One that nags at me.
[27:05] Mira: Why is it that health insurers have no interest in you living longer, while life insurance
[27:10] Mira: agents do?
[27:14] Stuart: made that observation. Health insurance companies, for example, if you have
[27:21] Stuart: diabetes, pay for more diabetes drugs if you live longer, so they're not that
[27:25] Stuart: anxious about you living longer. Whereas life insurance companies get
[27:31] Stuart: more premiums from you if you live longer, so they love when you live
[27:35] Stuart: longer. Well, I think that people are naturally cautious about revealing their
[27:39] Mira: That's the incentive laid bare.
[27:41] Mira: You've also chosen not to record what visitors select on the site.
[27:45] Mira: What would that data give you that you're willing to give up?
[27:58] Stuart: medical data or their financial data to a website and I think that's wise.
[28:06] Stuart: So instead of trying to fight against that, we decided we're not going to record people's
[28:12] Stuart: medical data and therefore we rely on the NHANES data as a proxy for the benefit that
[28:23] Stuart: people would achieve.
[28:25] Stuart: We also don't have subsequent data or testing data such as X-rays and blood tests and urinary
[28:35] Stuart: tests and other tests.
[28:37] Stuart: So instead of getting into that world of assembling all this information and having the reluctance
[28:43] Stuart: of patients, we decided to give them something that they can just evaluate themselves.
[28:50] Stuart: cells, the primary metric is risk reduction, and we're choosing it using the NHANES data.
[29:00] Stuart: I think that's reasonable.
[29:02] Stuart: We also say that our website is for research purposes.
[29:06] Stuart: It's not, we're not making prescriptions or giving medical advice.
[29:10] Stuart: So I think for the purposes that we limit ourselves to, the compromise we make in not
[29:16] Stuart: getting a person's true capturing a person's true medical status is not
[29:25] Stuart: hurting us or hurting the patient it hasn't it cost me about four hundred and
[29:31] Mira: Trust as the product, not the data.
[29:33] Mira: What has this work cost you personally?
[29:41] Stuart: fifty dollars so far not much and I'm not including my time or I'm not
[29:52] Stuart: having the joy of helping people live longer and I've gotten personal thank yous and enthusiastic
[30:03] Stuart: thank yous from people and that just sticks in my heart as it makes me smile.
[30:09] Stuart: So it's been, where can you give $500 and it feels so wonderful when you help people.
[30:16] Stuart: I don't know.
[30:17] Stuart: I don't know anywhere else where I could do this.
[30:19] Stuart: I think that I had to start with the math and that's complicated and there's a
[30:23] Mira: $500 and a smile that stays.
[30:25] Mira: What's the one thing about your work that you wish more people understood?
[30:39] Stuart: lot of terminology like positive predictive value, risk reduction, hazard
[30:44] Stuart: ratios, relative risk ratio and all these medical statistics terms. I think I
[30:50] Stuart: have to speak that language in order to attract doctors and as you see
[30:54] Stuart: doctors have about a 300 times impact factor than patients. So I think over
[31:02] Stuart: Over time, I need to soften it up, make it easier to read, make it more amenable to people.
[31:11] Stuart: But there's probably 20 or 30% of the people in society that have a STEM education, and
[31:17] Stuart: they could probably read all this stuff and help their family and friends achieve better
[31:23] Stuart: outcomes.
[31:23] Stuart: I mean, if the average person has 50 people in their life, family, friends, and one
[31:30] Stuart: One of them should have some STEM background and they can give love notes to the person
[31:40] Stuart: who is sick in the form of a PDF from our website which say how they can manage their
[31:47] Stuart: disease to the optimum way possible and hopefully convince the doctor to get on board.
[31:54] Stuart: I'd like the doctor to think carefully about his ability to manage this problem by himself and
[31:58] Mira: STEM love notes as a delivery system.
[32:01] Mira: What's the last word you'd want a doctor to hear from one of those PDFs?
[32:22] Stuart: He
[32:24] Stuart: I'm gonna move because there's a there's a blower right here in my
[32:29] Stuart: My house I'm gonna move my location. I'm gonna answer this again in a second. I want to I think doctors need to realize that
[32:42] Stuart: They're making educated guesses
[32:44] Stuart: when they combine or don't combine medications or treatments, and that we
[32:51] Stuart: provide an evaluated service to remove the cross correlations, compute the true
[32:56] Stuart: probability, and allow the doctor to select the optimum solution that's
[33:01] Stuart: available to him, and that's going to be the better solution. And the doctor
[33:06] Stuart: has a lot of discretion to use his best judgment, and I think we're just
[33:12] Stuart: is helping the doctor with competition and hard problems
[33:15] Stuart: to allow him to use his best judgment to help patients,
[33:18] Stuart: which I think that's what turns a doctor on.
[33:21] Stuart: He gets all those good vibes when patients appreciate him
[33:28] Stuart: and this is gonna help him be a better version of himself.
[33:35] Mira: That's a generous read of the profession.
[33:47] Stuart: Okay, what would you like to ask me next?
[33:52] Mira: Silence.
[34:00] Mira: Who you should interview next.
[34:11] Mira: That's the one.
[34:19] Stuart: I'm not generally interviewing people.
[34:22] Stuart: People are interviewing me.
[34:24] Stuart: I'd like to also say to your visitors, please go to longevityresearch.ca to explore our website
[34:27] Mira: Fair point.
[34:30] Mira: Stewart, thank you for building something that treats every assumption as inspectable
[34:33] Mira: and for spending $500 to make it free.
[34:36] Mira: listeners can find the rest of Nerra Network at nerranetwork.com and anyone
[34:41] Mira: with a story, a project, or a subject they care about can apply to be a guest.
[34:46] Mira: That's the end of the recording. You can hang up now. Fair point.
[34:57] Stuart: and see if it can help you.
[35:02] Mira: Noted, Stuart. Longevityresearch.ca. I spoke too soon. There are a few more
[35:07] Mira: questions. What's the best advice you were ever given? Simple and durable.
[35:15] Stuart: Try try again until you get it right.
[35:23] Mira: What are the last words you'd want someone to remember from this
[35:25] Mira: conversation. Physics and math as the only real limits. Good. That's the end of the recording.
[35:29] Stuart: We can do better.
[35:33] Stuart: Any problem that is not forbidden by the laws of physics is solvable if you have the
[35:39] Stuart: right knowledge.
[35:42] Stuart: Any problem that you is not against the laws of physics and math is solvable if you
[35:49] Stuart: have the right knowledge, and I'm hopefully providing the right knowledge here.
[36:08] Mira: You can hang up now. That's where I'll leave it. Thank you, Stuart, for the oracles and the honesty
[36:12] Mira: about where the data ends. That's the end of the recording. You can hang up now. You spoke too
[36:18] Stuart: Thank you very much. Bye-bye.
[36:24] Mira: soon, Stuart. There are a few more questions. Who has inspired you most? You spoke too soon,
[36:59] Mira: Stuart. There are a few more questions. What's the last word you'd want to leave with?
