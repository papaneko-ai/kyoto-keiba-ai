"""Deterministic, no-bet 100-yen budget allocation for UI-only planning."""

def allocate(budget,weights):
 if type(budget) is not int or budget<0 or budget>1_000_000 or budget%100:
  raise ValueError("budget_must_be_100_yen_increment")
 if not isinstance(weights,(list,tuple)) or not 1<=len(weights)<=4:
  raise ValueError("one_to_four_candidate_ratios_required")
 if any(type(w) is not int or not 0<=w<=100 for w in weights):
  raise ValueError("invalid_ratio")
 total=sum(weights)
 if total==0 or budget==0:return [0]*len(weights)
 units=budget//100
 numerators=[units*w for w in weights]
 base=[n//total for n in numerators]
 remaining=units-sum(base)
 for i in sorted(range(len(weights)),key=lambda i:(-(numerators[i]%total),i))[:remaining]:
  base[i]+=1
 amounts=[v*100 for v in base]
 if sum(amounts)>budget:raise AssertionError("budget_exceeded")
 return amounts
